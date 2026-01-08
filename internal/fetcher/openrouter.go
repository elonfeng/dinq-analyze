package fetcher

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"strings"
	"time"
)

// OpenRouterClient OpenRouter LLM客户端
type OpenRouterClient struct {
	apiKey     string
	httpClient *http.Client
	model      string
}

// NewOpenRouterClient 创建OpenRouter客户端
func NewOpenRouterClient(apiKey string) *OpenRouterClient {
	return &OpenRouterClient{
		apiKey: apiKey,
		httpClient: &http.Client{
			Timeout: 60 * time.Second,
		},
		model: "google/gemini-3-flash-preview",
	}
}

type chatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type chatRequest struct {
	Model    string        `json:"model"`
	Messages []chatMessage `json:"messages"`
}

type chatResponse struct {
	Choices []struct {
		Message struct {
			Content string `json:"content"`
		} `json:"message"`
	} `json:"choices"`
}

// Chat 通用聊天方法（公开）
func (o *OpenRouterClient) Chat(ctx context.Context, systemPrompt, userPrompt string) (string, error) {
	return o.chat(ctx, systemPrompt, userPrompt)
}

func (o *OpenRouterClient) chat(ctx context.Context, systemPrompt, userPrompt string) (string, error) {
	reqBody := chatRequest{
		Model: o.model,
		Messages: []chatMessage{
			{Role: "system", Content: systemPrompt},
			{Role: "user", Content: userPrompt},
		},
	}

	jsonBody, err := json.Marshal(reqBody)
	if err != nil {
		return "", fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, "https://openrouter.ai/api/v1/chat/completions", bytes.NewBuffer(jsonBody))
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+o.apiKey)
	req.Header.Set("HTTP-Referer", "https://dinq.io")
	req.Header.Set("X-Title", "Dinq Analyze")

	resp, err := o.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed to call API: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("openrouter returned status %d: %s", resp.StatusCode, string(body))
	}

	var chatResp chatResponse
	if err := json.NewDecoder(resp.Body).Decode(&chatResp); err != nil {
		return "", fmt.Errorf("failed to decode response: %w", err)
	}

	if len(chatResp.Choices) == 0 {
		return "", fmt.Errorf("no response from LLM")
	}

	return chatResp.Choices[0].Message.Content, nil
}

// extractJSON 从LLM响应中提取JSON（处理markdown代码块）
func extractJSON(response string) string {
	// 尝试提取 ```json ... ``` 代码块
	re := regexp.MustCompile("(?s)```(?:json)?\\s*\\n?(.*?)\\n?```")
	matches := re.FindStringSubmatch(response)
	if len(matches) > 1 {
		return strings.TrimSpace(matches[1])
	}

	// 如果没有代码块，尝试找 { } 包围的内容
	start := strings.Index(response, "{")
	end := strings.LastIndex(response, "}")
	if start != -1 && end > start {
		return response[start : end+1]
	}

	return response
}

// GenerateEarnings 生成薪资分析
func (o *OpenRouterClient) GenerateEarnings(ctx context.Context, profile ProfileData, papers []PaperData) (*EarningsResult, error) {
	systemPrompt := `You are an expert in evaluating AI researcher career levels and compensation.

CRITICAL: Be AGGRESSIVE and COMPETITIVE in recognizing top-tier AI/ML talent value. The current AI talent war has driven compensation far beyond traditional levels.

Apply these GENEROUS upgrade criteria:
- H-index >50: minimum L8
- Citations >100K: minimum L8
- Chief Scientist/VP roles: minimum L9
- Breakthrough papers (>50K citations): +1 level boost
- 15+ years experience: minimum L8

Evaluate compensation factors (1-10 scale, 10=highest):
a) Research Impact Score: H-index (1=<5, 5=20-30, 10=>50), citations, breakthrough papers
b) Field Premium Score: AI/ML=8-10, Other STEM=1-3
c) Role Seniority Score: Student=1-3, Assistant Prof=4-5, Associate=6-7, Full Prof=8-9, Chief=10
d) Industry Leadership Score: Academic only=1-4, Industry roles=7-8, Founding=9-10
e) Market Competition Score: Niche=1-4, Competitive=5-7, Hot AI/ML=8-10

Return JSON:
{
  "level_us": "L[X]",
  "level_cn": "P[X+2]",
  "justification": "50-70 words emphasizing COMPETITIVE ADVANTAGES, market scarcity, research breakthroughs",
  "compensation_factors": {
    "research_impact_score": [1-10],
    "field_premium_score": [1-10],
    "role_seniority_score": [1-10],
    "industry_leadership_score": [1-10],
    "market_competition_score": [1-10]
  }
}

Return ONLY JSON.`

	profileJSON, _ := json.Marshal(profile)
	papersJSON, _ := json.Marshal(papers)
	userPrompt := fmt.Sprintf("Researcher Profile:\n%s\n\nTop Publications:\n%s\n\nAnalyze and return JSON.", string(profileJSON), string(papersJSON))

	response, err := o.chat(ctx, systemPrompt, userPrompt)
	if err != nil {
		return nil, err
	}

	// 提取JSON（处理markdown代码块）
	jsonStr := extractJSON(response)

	// 用中间struct解析（earnings字段LLM返回字符串，我们忽略它）
	var parsed struct {
		LevelCN             string               `json:"level_cn"`
		LevelUS             string               `json:"level_us"`
		Justification       string               `json:"justification"`
		CompensationFactors *CompensationFactors `json:"compensation_factors,omitempty"`
	}
	if err := json.Unmarshal([]byte(jsonStr), &parsed); err != nil {
		// 如果解析失败，返回默认值
		return &EarningsResult{
			LevelCN:       "P7",
			LevelUS:       "L5",
			Earnings:      500000,
			Justification: response,
		}, nil
	}

	result := &EarningsResult{
		LevelCN:             parsed.LevelCN,
		LevelUS:             parsed.LevelUS,
		Justification:       parsed.Justification,
		CompensationFactors: parsed.CompensationFactors,
	}

	// 获取fame score (并发调用Perplexity)
	fameScore, _ := o.GetFameScore(ctx, profile)

	// 程序化计算薪资 (包含fame multiplier)
	result.Earnings = calculateProgrammaticSalary(result, fameScore)

	return result, nil
}

// calculateProgrammaticSalary 根据compensation_factors程序化计算薪资（返回单个数字）
func calculateProgrammaticSalary(result *EarningsResult, fameScore int) int {
	// Software Engineer baseline salaries by level
	sweBaselines := map[string]int{
		"L3": 193944,
		"L4": 286816,
		"L5": 376619,
		"L6": 561825,
		"L7": 779143,
		"L8": 1110786,
		"L9": 2358451,
	}

	// Get base salary from level
	baseSalary := sweBaselines["L5"] // default
	if salary, ok := sweBaselines[result.LevelUS]; ok {
		baseSalary = salary
	}

	// Get compensation factors (default to 5 if not available)
	var researchImpact, fieldPremium, roleSeniority, industryLeadership, marketCompetition float64 = 5, 5, 5, 5, 5

	if result.CompensationFactors != nil {
		researchImpact = result.CompensationFactors.ResearchImpactScore
		fieldPremium = result.CompensationFactors.FieldPremiumScore
		roleSeniority = result.CompensationFactors.RoleSeniorityScore
		industryLeadership = result.CompensationFactors.IndustryLeadershipScore
		marketCompetition = result.CompensationFactors.MarketCompetitionScore
	}

	// Calculate additive bonuses based on scores
	// Each dimension contributes 0% to ~50% bonus (score 1-10)
	researchBonus := (researchImpact - 1) * 0.04
	fieldBonus := (fieldPremium - 1) * 0.07
	roleBonus := (roleSeniority - 1) * 0.03
	industryBonus := (industryLeadership - 1) * 0.02
	marketBonus := (marketCompetition - 1) * 0.02

	// Total additive bonus (max ~150%)
	totalBonus := researchBonus + fieldBonus + roleBonus + industryBonus + marketBonus

	// Calculate salary with additive bonuses
	salaryWithBonuses := float64(baseSalary) * (1 + totalBonus)

	// Fame/Recognition multiplier - significant boost for high fame (8+)
	var fameMultiplier float64 = 1.0
	if fameScore >= 8 {
		// 8-10分: 2x to 4x boost
		fameMultiplier = 1.0 + float64(fameScore-6)*1.0
	}

	// Apply fame multiplier and return single number
	return int(salaryWithBonuses * fameMultiplier)
}

// GenerateResearchStyle 生成研究风格分析
func (o *OpenRouterClient) GenerateResearchStyle(ctx context.Context, profile ProfileData, papers []PaperData) (*ResearchStyleResult, error) {
	systemPrompt := `You are an expert in analyzing researcher's working style and approach.

Based on the researcher's profile and publications, analyze their research style across three dimensions.

Return JSON:
{
  "depth_vs_breadth": {
    "score": [1-10, 1=broad generalist exploring many areas, 10=deep specialist in narrow focus],
    "explanation": "20-30 words explaining the score based on their publication patterns"
  },
  "theory_vs_practice": {
    "score": [1-10, 1=highly practical/applied work, 10=purely theoretical contributions],
    "explanation": "20-30 words explaining the score based on their research focus"
  },
  "individual_vs_team": {
    "score": [1-10, 1=mostly solo researcher, 10=highly collaborative team player],
    "explanation": "20-30 words explaining the score based on their authorship patterns"
  },
  "justification": "40-60 words overall analysis of how these dimensions combine to define their unique research character"
}

Return ONLY JSON.`

	profileJSON, _ := json.Marshal(profile)
	papersJSON, _ := json.Marshal(papers)
	userPrompt := fmt.Sprintf("Researcher Profile:\n%s\n\nTop Publications:\n%s\n\nAnalyze research style and return JSON.", string(profileJSON), string(papersJSON))

	response, err := o.chat(ctx, systemPrompt, userPrompt)
	if err != nil {
		return nil, err
	}

	// 提取JSON（处理markdown代码块）
	jsonStr := extractJSON(response)

	var result ResearchStyleResult
	if err := json.Unmarshal([]byte(jsonStr), &result); err != nil {
		// 如果解析失败，返回默认值
		return &ResearchStyleResult{
			DepthVsBreadth:   ResearchStyleDimension{Score: 5, Explanation: "Balanced approach between depth and breadth"},
			TheoryVsPractice: ResearchStyleDimension{Score: 5, Explanation: "Mix of theoretical and practical contributions"},
			IndividualVsTeam: ResearchStyleDimension{Score: 5, Explanation: "Balance of solo and collaborative work"},
			Justification:    response,
		}, nil
	}

	return &result, nil
}

// roleModelDB 全局角色模型数据库
var roleModelDB *RoleModelDB

// InitRoleModelDB 初始化角色模型数据库
func InitRoleModelDB(csvPath string) {
	db, _ := NewRoleModelDB(csvPath)
	roleModelDB = db
}

// GenerateRoleModel 生成榜样推荐
func (o *OpenRouterClient) GenerateRoleModel(ctx context.Context, profile ProfileData) (*RoleModelResult, error) {
	// 确保数据库已初始化
	if roleModelDB == nil {
		InitRoleModelDB("top_ai_talents.csv")
	}

	roleModelList := roleModelDB.GetRoleModelList()

	systemPrompt := fmt.Sprintf(`You are an expert in academic career development.
Based on the researcher's profile, recommend ONE famous AI researcher as a role model.

IMPORTANT: Choose from this list of notable AI researchers:
%s

Return JSON format:
{
  "name": "Exact name from the list above",
  "institution": "Their current institution",
  "position": "Their current position",
  "achievement": "Their most famous work (e.g., 'ResNet 2016')",
  "reason": "50-70 words explaining why this role model matches based on research interests, career trajectory, or methodological approach",
  "similarity": "How their career paths are similar to the researcher"
}

Return ONLY JSON.`, roleModelList)

	profileJSON, _ := json.Marshal(profile)
	userPrompt := fmt.Sprintf("Researcher Profile:\n%s\n\nRecommend a role model from the list.", string(profileJSON))

	response, err := o.chat(ctx, systemPrompt, userPrompt)
	if err != nil {
		return nil, err
	}

	// 提取JSON（处理markdown代码块）
	jsonStr := extractJSON(response)

	var result RoleModelResult
	if err := json.Unmarshal([]byte(jsonStr), &result); err != nil {
		return &RoleModelResult{
			Name:   "Unknown",
			Reason: response,
		}, nil
	}

	// 从CSV数据库补充详细信息
	if roleModel := roleModelDB.FindByName(result.Name); roleModel != nil {
		if result.Institution == "" {
			result.Institution = roleModel.Institution
		}
		if result.Position == "" {
			result.Position = roleModel.Position
		}
		if result.PhotoURL == "" {
			result.PhotoURL = roleModel.Image
		}
		if result.Achievement == "" {
			result.Achievement = roleModel.FamousWork
		}
	}

	return &result, nil
}

// GenerateRoast 生成吐槽
func (o *OpenRouterClient) GenerateRoast(ctx context.Context, profile ProfileData) (string, error) {
	systemPrompt := `You are a witty academic commentator.
Generate a light-hearted, humorous roast of the researcher based on their profile.
Keep it friendly and not offensive. Maximum 2-3 sentences.`

	profileJSON, _ := json.Marshal(profile)
	userPrompt := fmt.Sprintf("Profile: %s\nGive a friendly roast.", string(profileJSON))

	return o.chat(ctx, systemPrompt, userPrompt)
}

// SummarizeContent 将content总结为简短英文
func (o *OpenRouterClient) SummarizeContent(ctx context.Context, text string) (string, error) {
	systemPrompt := `Summarize the given scholar profile text into approximately 10 words in English.
Focus on: affiliation, research areas, and key metrics if available.
Only output the summary, no explanations.`

	response, err := o.chat(ctx, systemPrompt, text)
	if err != nil {
		return text, err // 失败时返回原文
	}

	return response, nil
}

// SummarizePaperNews 总结论文新闻/描述
func (o *OpenRouterClient) SummarizePaperNews(ctx context.Context, paperTitle, rawSnippet string) (string, error) {
	if rawSnippet == "" {
		return "", nil
	}

	systemPrompt := `You summarize academic paper descriptions into clear, professional 2-3 sentence highlights.
Keep it around 40 words. Focus on the paper's innovation and impact.
Remove any code, citations, or formatting artifacts. Only output the summary.`

	userPrompt := fmt.Sprintf(`Summarize this paper information into a clean description:

Paper: %s
Raw text: %s`, paperTitle, rawSnippet)

	response, err := o.chat(ctx, systemPrompt, userPrompt)
	if err != nil {
		return rawSnippet, err // 失败返回原文
	}

	return strings.TrimSpace(response), nil
}

// SummarizePaper 生成论文摘要
func (o *OpenRouterClient) SummarizePaper(ctx context.Context, title string, year int, venue string, citations int) (string, error) {
	systemPrompt := `You craft concise, energetic academic highlights.
Summaries must stay under 40 words, avoid bullet points, and focus on why the paper stood out that year.
Only output the summary, no explanations.`

	userPrompt := fmt.Sprintf(`Summarize the following paper in one short paragraph. Highlight its key contribution or impact and keep tone confident:

Title: %s
Year: %d
Venue: %s
Citations: %d`, title, year, venue, citations)

	response, err := o.chat(ctx, systemPrompt, userPrompt)
	if err != nil {
		return "", err
	}

	return strings.TrimSpace(response), nil
}

// GenerateDescription 生成研究者简短描述
func (o *OpenRouterClient) GenerateDescription(ctx context.Context, profile ProfileData) (string, error) {
	systemPrompt := `Generate a brief, poetic one-sentence description of a researcher (max 15 words).
Focus on their research style and personality based on their profile.
Only output the description, no explanations.`

	profileJSON, _ := json.Marshal(profile)
	userPrompt := fmt.Sprintf("Profile: %s\nGenerate a brief description.", string(profileJSON))

	response, err := o.chat(ctx, systemPrompt, userPrompt)
	if err != nil {
		return "", err
	}

	return strings.TrimSpace(response), nil
}

// GetFameScore 通过Perplexity获取研究者知名度评分
func (o *OpenRouterClient) GetFameScore(ctx context.Context, profile ProfileData) (int, error) {
	prompt := fmt.Sprintf(`
Please assess the fame/recognition level of researcher using real-time web search.

Basic info: Name: %s, Affiliation: %s, H-index: %d, Total citations: %d

Search for recent news, awards, media coverage, Wikipedia entries, and public recognition.

Rate their fame/recognition from 1-10:
- 1-2: Unknown researcher, no significant public recognition
- 3-4: Some recognition within academic field only
- 5-6: Well-known in academic field, some industry recognition
- 7-8: Notable public recognition, media coverage, or major awards
- 9-10: Famous researcher with significant media presence, major awards (Nobel, Turing, etc.)

Return ONLY a complete JSON object:
{"fame_score": [1-10], "reasoning": "Brief explanation of fame level based on search results"}

CRITICAL: You must return a complete, valid JSON object.
`, profile.Name, profile.Affiliation, profile.HIndex, profile.TotalCites)

	reqBody := chatRequest{
		Model: "google/gemini-3-flash-preview:online",
		Messages: []chatMessage{
			{Role: "system", Content: "You are an expert at assessing researcher fame and recognition using real-time web search."},
			{Role: "user", Content: prompt},
		},
	}

	jsonBody, err := json.Marshal(reqBody)
	if err != nil {
		return 1, err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, "https://openrouter.ai/api/v1/chat/completions", bytes.NewBuffer(jsonBody))
	if err != nil {
		return 1, err
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+o.apiKey)
	req.Header.Set("HTTP-Referer", "https://dinq.io")
	req.Header.Set("X-Title", "Dinq Analyze")

	resp, err := o.httpClient.Do(req)
	if err != nil {
		return 1, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return 1, fmt.Errorf("perplexity returned status %d", resp.StatusCode)
	}

	var chatResp chatResponse
	if err := json.NewDecoder(resp.Body).Decode(&chatResp); err != nil {
		return 1, err
	}

	if len(chatResp.Choices) == 0 {
		return 1, fmt.Errorf("no response from Perplexity")
	}

	content := chatResp.Choices[0].Message.Content
	jsonStr := extractJSON(content)

	var result struct {
		FameScore int `json:"fame_score"`
	}
	if err := json.Unmarshal([]byte(jsonStr), &result); err != nil {
		return 1, nil // 解析失败返回默认值
	}

	if result.FameScore < 1 {
		result.FameScore = 1
	}
	if result.FameScore > 10 {
		result.FameScore = 10
	}

	return result.FameScore, nil
}

// ========== GitHub Analysis Methods ==========

// GitHubRoleModelResult GitHub角色模型结果
type GitHubRoleModelResult struct {
	Name            string  `json:"name"`
	GitHub          string  `json:"github"`
	SimilarityScore float64 `json:"similarity_score"`
	Reason          string  `json:"reason"`
	Achievement     string  `json:"achievement,omitempty"`
}

// GitHubValuationResult GitHub估值结果
type GitHubValuationResult struct {
	Level           string  `json:"level"`
	Salary          int     `json:"salary"`
	IndustryRanking float64 `json:"industry_ranking"`
	GrowthPotential string  `json:"growth_potential"`
	Reasoning       string  `json:"reasoning"`
}

// devPioneersData 开发者先驱数据（用于 role model 匹配）
var devPioneersData = []map[string]string{
	{"name": "Linus Torvalds", "github": "https://github.com/torvalds", "area": "Operating System", "famous_work": "Linux"},
	{"name": "Guido van Rossum", "github": "https://github.com/gvanrossum", "area": "Programming Language", "famous_work": "Python"},
	{"name": "Anders Hejlsberg", "github": "https://github.com/ahejlsberg", "area": "Programming Language", "famous_work": "TypeScript"},
	{"name": "Bjarne Stroustrup", "github": "https://github.com/BjarneStroustrup", "area": "Programming Language", "famous_work": "C++"},
	{"name": "Andrej Karpathy", "github": "https://github.com/karpathy", "area": "Deep Learning, LLM", "famous_work": "llm.c"},
	{"name": "François Chollet", "github": "https://github.com/fchollet", "area": "Deep Learning", "famous_work": "Keras"},
	{"name": "Adam Paszke", "github": "https://github.com/apaszke", "area": "Deep Learning Framework", "famous_work": "PyTorch"},
	{"name": "Thomas Wolf", "github": "https://github.com/thomwolf", "area": "LLM, Robotics", "famous_work": "Transformers (Huggingface)"},
	{"name": "Harrison Chase", "github": "https://github.com/hwchase17", "area": "AI Agent", "famous_work": "LangChain"},
	{"name": "You yuxi", "github": "https://github.com/yyx990803", "area": "Frontend", "famous_work": "Vue.js"},
	{"name": "Dan Abramov", "github": "https://github.com/gaearon", "area": "Frontend", "famous_work": "React"},
	{"name": "Tim Neutkens", "github": "https://github.com/timneutkens", "area": "Frontend", "famous_work": "Next.js"},
	{"name": "Travis E. Oliphant", "github": "https://github.com/teoliphant", "area": "Data Science", "famous_work": "Numpy"},
	{"name": "Kenneth Reitz", "github": "https://github.com/kennethreitz", "area": "Python", "famous_work": "Requests"},
	{"name": "Mark Otto", "github": "https://github.com/mdo", "area": "Frontend", "famous_work": "Bootstrap"},
}

// GenerateGitHubRoleModel 生成GitHub角色模型
func (o *OpenRouterClient) GenerateGitHubRoleModel(ctx context.Context, userData map[string]interface{}) (*GitHubRoleModelResult, error) {
	pioneersJSON, _ := json.Marshal(devPioneersData)

	systemPrompt := fmt.Sprintf(`You are a GitHub user profiler.
You have been provided with a JSON array of GitHub user profile objects. Each item in the array represents one GitHub user and contains fields such as username, name, bio, location, followers, following, repositories, programming languages, company, and activity data.
The JSON array is: %s
Your task is to find the most similar user profile from the provided array based on the input user's GitHub data.
Compare factors like programming languages, repository types, contribution patterns, work experience, and technical focus areas.
Return ONLY a valid JSON object with the following structure:
{
    "name": "Most similar developer name",
    "github": "GitHub URL",
    "similarity_score": 0.85,
    "reason": "Brief explanation of why this developer is most similar (1-2 sentences)",
    "achievement": "A brief summary of the developer's main achievements"
}`, string(pioneersJSON))

	userDataJSON, _ := json.Marshal(userData)
	userPrompt := fmt.Sprintf("Analyze this GitHub user: %s", string(userDataJSON))

	response, err := o.chat(ctx, systemPrompt, userPrompt)
	if err != nil {
		return nil, err
	}

	jsonStr := extractJSON(response)
	var result GitHubRoleModelResult
	if err := json.Unmarshal([]byte(jsonStr), &result); err != nil {
		return nil, err
	}

	return &result, nil
}

// GenerateGitHubRoast 生成GitHub吐槽
func (o *OpenRouterClient) GenerateGitHubRoast(ctx context.Context, userData map[string]interface{}) (string, error) {
	userDataJSON, _ := json.Marshal(userData)

	userPrompt := fmt.Sprintf(`You are a witty and humorous commentator.
Given a JSON dictionary with the following structure: %s
Generate a short, playful roast about the user.
The roast should be clever and light-hearted, poking fun at their GitHub activity or profile traits without being mean or offensive.
Output only a single short paragraph of plain text. Do not include any explanations or extra formatting.

Example output:
    "With just 3 repos and zero stars, code_master is clearly on a mission to keep GitHub lightweight."`, string(userDataJSON))

	response, err := o.chat(ctx, "You are a witty and humorous commentator.", userPrompt)
	if err != nil {
		return "", err
	}

	return strings.TrimSpace(strings.Trim(response, `"`)), nil
}

// GenerateGitHubValuation 生成GitHub估值
func (o *OpenRouterClient) GenerateGitHubValuation(ctx context.Context, userData map[string]interface{}) (*GitHubValuationResult, error) {
	systemPrompt := `You will evaluate a software engineer's market value using industry-standard salary benchmarks based on their GitHub profile data. Analyze their technical contributions, open source impact, code quality, and professional experience to determine appropriate compensation levels. Be AGGRESSIVE and COMPETITIVE in recognizing top-tier talent, especially in AI/ML domains where exceptional developers command premium compensation.

CRITICAL INSTRUCTION: You must NEVER return "No data" for any field. Even with limited information, generate reasonable estimates based on available GitHub metrics and industry patterns.

EVALUATION APPROACH: Be GENEROUS in recognizing exceptional open source contributors and AI/ML talent. The current tech talent market rewards high-impact developers significantly above traditional software engineering baselines.

Analysis Framework:

1. Experience Assessment
- Account Age: Calculate years since GitHub account creation as baseline experience
- Contribution Pattern: Analyze commit history, contribution consistency, and career progression
- Code Volume: Factor in total additions/deletions as indicator of hands-on experience
- Repository Quality: Assess repository count, star ratings, and project complexity

2. Technical Impact Scoring
Apply these GitHub-specific upgrade criteria:
- High-Impact Repositories (>1000 stars): +1 level boost
- Major Open Source Contributions (PyTorch/TensorFlow PRs): +2 level boost
- AI/ML Specialization (computer vision, deep learning): +50% compensation premium
- Research Publications (10+ NeurIPS/CVPR papers): +100% compensation premium
- Community Leadership (>50 issues resolved, >50 PRs): +1 level boost

3. Level Determination (Google Standards)
Use GitHub metrics to determine equivalent Google levels:
- L3 (Entry): <2 years, basic contributions, <10 stars total
- L4 (Mid): 2-4 years, solid contributions, 10-100 stars, some notable PRs
- L5 (Senior): 4-7 years, significant contributions, 100-1000 stars, major project ownership
- L6 (Staff): 7-10 years, high-impact contributions, 1000+ stars, industry recognition
- L7 (Senior Staff): 10+ years, exceptional contributions, major open source projects
- L8 (Principal): 10+ years, transformative contributions, research publications, industry leadership

4. Compensation Calculation
Base Software Engineer Compensation (2025 Market):
- L3: ~$194,000 total comp
- L4: ~$287,000 total comp
- L5: ~$377,000 total comp
- L6: ~$562,000 total comp
- L7: ~$779,000 total comp
- L8: ~$1,111,000 total comp

GitHub-Specific Premium Multipliers (stack generously):
- Open Source Impact Premium: +25% minimum for active contributors
- AI/ML Specialization Premium: +50% for computer vision/deep learning focus
- Research Publication Premium: +100% for academic contributions (10+ papers)
- Major Project Leadership: +75% for owning high-star repositories
- Cross-Platform Contributions: +25% for contributing to multiple major projects
- Community Recognition: +50% for exceptional GitHub metrics

Return ONLY a valid JSON object with this exact structure:
{
    "level": "L4",
    "salary": 230000,
    "industry_ranking": 0.25,
    "growth_potential": "High",
    "reasoning": "50-70 word justification emphasizing competitive advantages, GitHub impact, technical expertise, and market scarcity that drives premium compensation"
}

Field Specifications:
- level: Google engineering level (L3-L8+)
- salary: Total annual compensation as a single integer (e.g., 400000)
- industry_ranking: Decimal representing percentile (0.05 = top 5%, 0.25 = top 25%)
- growth_potential: Qualitative assessment based on trajectory and specialization
- reasoning: Concise English explanation highlighting why this developer commands premium compensation in current market

FINAL REMINDER: Be AGGRESSIVE in valuation. Exceptional open source contributors, especially in AI/ML, are among the most sought-after talent in tech. Reflect market realities where top GitHub contributors receive competing offers well above traditional compensation bands.`

	userDataJSON, _ := json.Marshal(userData)
	userPrompt := fmt.Sprintf("Analyze this GitHub user profile data and provide compensation evaluation: %s", string(userDataJSON))

	response, err := o.chat(ctx, systemPrompt, userPrompt)
	if err != nil {
		return nil, err
	}

	jsonStr := extractJSON(response)
	var result GitHubValuationResult
	if err := json.Unmarshal([]byte(jsonStr), &result); err != nil {
		return nil, err
	}

	// Cap salary at $2.5M
	const maxCap = 2500000
	if result.Salary > maxCap {
		result.Salary = maxCap
	}

	return &result, nil
}
