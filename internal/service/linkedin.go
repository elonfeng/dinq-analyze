package service

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"regexp"
	"strings"
	"sync"
	"time"

	"dinq-analyze-go/internal/cache"
	"dinq-analyze-go/internal/fetcher"
	"dinq-analyze-go/internal/model"
	"dinq-analyze-go/internal/sse"
)

// LinkedInCacheTTL LinkedIn缓存过期时间
const LinkedInCacheTTL = 24 * time.Hour

// LinkedInService LinkedIn分析服务
type LinkedInService struct {
	linkedinClient   *fetcher.LinkedInClient
	openRouterAPIKey string
	httpClient       *http.Client
	cache            cache.Cache
}

// NewLinkedInService 创建LinkedIn服务
func NewLinkedInService(tavilyAPIKey, apifyAPIKey, openRouterAPIKey string, c cache.Cache) *LinkedInService {
	return &LinkedInService{
		linkedinClient:   fetcher.NewLinkedInClient(tavilyAPIKey, apifyAPIKey),
		openRouterAPIKey: openRouterAPIKey,
		httpClient: &http.Client{
			Timeout: 60 * time.Second,
		},
		cache: c,
	}
}

// AnalyzeWithSSE 执行LinkedIn分析并通过SSE推送结果
// candidateData: 用户选择的候选人数据 {linkedin_id, name, content, url}
func (s *LinkedInService) AnalyzeWithSSE(ctx context.Context, query string, candidateData map[string]interface{}, w *sse.LinkedInWriter) error {
	// Step 1: 确定LinkedIn URL
	var linkedinURL string
	var personName string
	var tavilyContent string // Tavily搜索返回的内容，用作about的fallback

	// 如果有候选人数据（用户选择的结果），直接使用
	var tavilyHeadline string // 从title提取的headline
	if candidateData != nil {
		if url, ok := candidateData["url"].(string); ok && url != "" {
			linkedinURL = url
		}
		if title, ok := candidateData["title"].(string); ok && title != "" {
			// title格式: "Keith Rabois - Khosla Ventures"，提取名字和headline
			personName = fetcher.ExtractLinkedInNameFromTitle(title)
			// 提取headline（" - " 后面的部分，去掉 " | LinkedIn"）
			title = strings.TrimSuffix(title, " | LinkedIn")
			title = strings.TrimSuffix(title, " - LinkedIn")
			if idx := strings.Index(title, " - "); idx > 0 {
				tavilyHeadline = strings.TrimSpace(title[idx+3:])
			}
		}
		if content, ok := candidateData["content"].(string); ok && content != "" {
			tavilyContent = content
		}
		log.Printf("[LinkedIn] Using candidate data: url=%s, name=%s, headline=%s", linkedinURL, personName, tavilyHeadline)
	}

	// 如果没有从candidateData获取到URL，走正常流程
	if linkedinURL == "" {
		if strings.Contains(query, "linkedin.com/in/") {
			// 直接使用提供的LinkedIn URL
			linkedinURL = query
			personName = fetcher.ExtractLinkedInID(query)
		} else {
			// 搜索LinkedIn
			personName = query
			w.SetAction(5, "Searching LinkedIn profile...")
			results, err := s.linkedinClient.SearchLinkedInURL(ctx, query)
			if err != nil {
				log.Printf("[LinkedIn] Search error: %v, trying direct URL", err)
			}

			if len(results) == 0 {
				// 没有搜索结果时，尝试直接拼接LinkedIn URL
				// 把空格替换为连字符，转小写，作为linkedin id尝试
				guessedID := strings.ToLower(strings.ReplaceAll(query, " ", "-"))
				linkedinURL = fmt.Sprintf("https://www.linkedin.com/in/%s", guessedID)
				log.Printf("[LinkedIn] No search results, trying direct URL: %s", linkedinURL)
			} else if len(results) > 1 {
				// 多个结果时让用户选择
				candidates := make([]model.LinkedInCandidate, 0, len(results))
				for _, r := range results {
					candidates = append(candidates, model.LinkedInCandidate{
						URL:     r.URL,
						Title:   r.Title,
						Content: r.Content,
						Score:   r.Score,
					})
				}
				w.SendCandidates(candidates)
				return nil // 等待用户选择
			} else {
				// 只有一个结果，直接使用
				linkedinURL = results[0].URL
				personName = fetcher.ExtractLinkedInNameFromTitle(results[0].Title)
				tavilyContent = results[0].Content
			}
		}
	}

	linkedinID := fetcher.ExtractLinkedInID(linkedinURL)
	if err := w.SetLinkedIn(linkedinID, personName); err != nil {
		log.Printf("[LinkedIn] Failed to send initial SSE: %v", err)
	}

	// 如果有Tavily数据，立即发送简版profile card（让前端秒显示）
	if tavilyHeadline != "" || tavilyContent != "" {
		partialProfile := &model.LinkedInProfileCard{
			LinkedInID: linkedinID,
			FullName:   personName,
			Headline:   tavilyHeadline,
			About:      tavilyContent,
			ProfileURL: linkedinURL,
		}
		w.SendCardDone(model.LinkedInCardProfile, partialProfile)
		log.Printf("[LinkedIn] Sent partial profile card from Tavily data")
	}

	// 检查缓存 (使用linkedinURL作为key)
	log.Printf("[LinkedIn] Checking cache with key: %s", linkedinURL)
	if s.cache != nil {
		cached, err := s.cache.Get(ctx, linkedinURL)
		if err == nil && cached != nil {
			log.Printf("[LinkedIn] Cache HIT for: %s", linkedinURL)
			w.SetAction(100, "Loaded from cache")
			return s.sendCachedResult(w, cached.Data, linkedinID, personName, linkedinURL)
		}
		log.Printf("[LinkedIn] Cache MISS for: %s (err=%v)", linkedinURL, err)
	}

	w.SetAction(10, "Fetching LinkedIn profile data...")

	// Step 2: 获取LinkedIn档案数据
	profileData, err := s.linkedinClient.FetchProfile(ctx, linkedinURL)
	if err != nil {
		return fmt.Errorf("failed to fetch LinkedIn profile: %w", err)
	}

	// 更新名字
	if fullName := profileData.GetFullName(); fullName != "" {
		personName = fullName
		_ = w.SetLinkedIn(linkedinID, personName) // 更新名字后再次发送
	}

	w.SetAction(20, "Analyzing profile...")

	// Step 3: 构建并发送Profile Card
	profileCard := s.buildProfileCard(profileData)
	w.SendCardDone(model.LinkedInCardProfile, profileCard)

	// Step 4: 并发执行所有AI分析，收集结果
	var (
		mu            sync.Mutex
		wg            sync.WaitGroup
		moneyResult   *model.LinkedInMoneyCard
		roastResult   string
		skillsResult  *model.LinkedInSkillsCard
		colleagResult *model.LinkedInColleaguesCard
		careerResult  *model.LinkedInCareerCard
		roleModelRes  *model.LinkedInRoleModelCard
		lifeResult    *model.LinkedInLifeWellBeingCard
	)

	wg.Add(7)

	// Money Card
	go func() {
		defer wg.Done()
		result, err := s.generateMoneyCard(ctx, profileData, personName)
		if err != nil {
			log.Printf("Money card error: %v", err)
			w.SendCardError(model.LinkedInCardMoney, err.Error())
			return
		}
		mu.Lock()
		moneyResult = result
		mu.Unlock()
		w.SendCardDone(model.LinkedInCardMoney, result)
	}()

	// Roast Card
	go func() {
		defer wg.Done()
		result, err := s.generateRoastCard(ctx, profileData, personName)
		if err != nil {
			log.Printf("Roast card error: %v", err)
			w.SendCardError(model.LinkedInCardRoast, err.Error())
			return
		}
		mu.Lock()
		roastResult = result.Roast
		mu.Unlock()
		w.SendCardDone(model.LinkedInCardRoast, result.Roast)
	}()

	// Skills Card
	go func() {
		defer wg.Done()
		result, err := s.generateSkillsCard(ctx, profileData, personName)
		if err != nil {
			log.Printf("Skills card error: %v", err)
			w.SendCardError(model.LinkedInCardSkills, err.Error())
			return
		}
		mu.Lock()
		skillsResult = result
		mu.Unlock()
		w.SendCardDone(model.LinkedInCardSkills, result)
	}()

	// Colleagues Card
	go func() {
		defer wg.Done()
		result, err := s.generateColleaguesCard(ctx, profileData, personName)
		if err != nil {
			log.Printf("Colleagues card error: %v", err)
			w.SendCardError(model.LinkedInCardColleagues, err.Error())
			return
		}
		mu.Lock()
		colleagResult = result
		mu.Unlock()
		w.SendCardDone(model.LinkedInCardColleagues, result)
	}()

	// Career Card
	go func() {
		defer wg.Done()
		result, err := s.generateCareerCard(ctx, profileData, personName)
		if err != nil {
			log.Printf("Career card error: %v", err)
			w.SendCardError(model.LinkedInCardCareer, err.Error())
			return
		}
		mu.Lock()
		careerResult = result
		mu.Unlock()
		w.SendCardDone(model.LinkedInCardCareer, result)
	}()

	// Role Model Card
	go func() {
		defer wg.Done()
		result, err := s.generateRoleModelCard(ctx, profileData, personName)
		if err != nil {
			log.Printf("Role model card error: %v", err)
			w.SendCardError(model.LinkedInCardRoleModel, err.Error())
			return
		}
		mu.Lock()
		roleModelRes = result
		mu.Unlock()
		w.SendCardDone(model.LinkedInCardRoleModel, result)
	}()

	// Life & Well-Being Card
	go func() {
		defer wg.Done()
		result, err := s.generateLifeWellBeingCard(ctx, profileData, personName)
		if err != nil {
			log.Printf("Life well-being card error: %v", err)
			w.SendCardError(model.LinkedInCardLifeWellBeing, err.Error())
			return
		}
		mu.Lock()
		lifeResult = result
		mu.Unlock()
		w.SendCardDone(model.LinkedInCardLifeWellBeing, result)
	}()

	// Step 5: 并发生成额外字段（与卡片生成同时进行）
	var (
		about          string
		personalTags   []string
		workExpSummary string
		eduSummary     string
	)

	wg.Add(4)

	go func() {
		defer wg.Done()
		about = s.generateAboutSummary(ctx, profileData, personName, tavilyContent)
	}()

	go func() {
		defer wg.Done()
		personalTags = s.generatePersonalTags(ctx, profileData, personName)
	}()

	go func() {
		defer wg.Done()
		workExpSummary = s.generateWorkExperienceSummary(ctx, profileData)
	}()

	go func() {
		defer wg.Done()
		eduSummary = s.generateEducationSummary(ctx, profileData)
	}()

	wg.Wait()

	// Step 6: 构建完整的profile_data (matches Python output)
	// 直接使用原始数据，保留所有字段
	rawProfile := s.buildFullRawProfile(profileData, linkedinURL)

	// 获取头像URL（优先使用profileData，回退到rawProfile）
	avatarURL := profileData.GetPhotoURL()
	if avatarURL == "" {
		// 尝试从rawProfile获取
		if pic, ok := rawProfile["profilePicHighQuality"].(string); ok && pic != "" {
			avatarURL = pic
		} else if pic, ok := rawProfile["profilePic"].(string); ok && pic != "" {
			avatarURL = pic
		}
	}
	log.Printf("[LinkedIn] Avatar URL: %s", avatarURL)

	// 收集所有卡片结果用于缓存
	mu.Lock()
	cacheData := map[string]interface{}{
		"profile_card":     profileCard,
		"money_card":       moneyResult,
		"roast":            roastResult,
		"skills_card":      skillsResult,
		"colleagues_card":  colleagResult,
		"career_card":      careerResult,
		"role_model_card":  roleModelRes,
		"life_well_being":  lifeResult,
		"about":            about,
		"personal_tags":    personalTags,
		"work_exp_summary": workExpSummary,
		"edu_summary":      eduSummary,
		"raw_profile":      rawProfile,
		"person_name":      personName,
		"avatar":           avatarURL,
	}
	mu.Unlock()

	finalProfileData := &model.LinkedInProfileData{
		RoleModel:             roleModelRes,
		MoneyAnalysis:         moneyResult,
		Roast:                 roastResult,
		Skills:                skillsResult,
		ColleaguesView:        colleagResult,
		Career:                careerResult,
		LifeWellBeing:         lifeResult,
		About:                 about,
		PersonalTags:          personalTags,
		WorkExperience:        rawProfile["experiences"], // 直接使用原始数据
		WorkExperienceSummary: workExpSummary,
		Education:             rawProfile["educations"], // 直接使用原始数据
		EducationSummary:      eduSummary,
		Avatar:                avatarURL,
		Name:                  personName,
		RawProfile:            rawProfile,
	}

	now := time.Now().UTC().Format(time.RFC3339Nano)
	finalResult := &model.LinkedInFinalResponse{
		Type:    "success",
		Message: "LinkedIn analysis completed",
		Data: &model.LinkedInAnalysisResult{
			LinkedInID:  linkedinID,
			PersonName:  personName,
			LinkedInURL: linkedinURL,
			ProfileData: finalProfileData,
			LastUpdated: now,
			CreatedAt:   now,
		},
	}

	// 缓存结果 (使用linkedinURL作为key)
	if s.cache != nil {
		if err := s.cache.Set(ctx, linkedinURL, cacheData, LinkedInCacheTTL); err != nil {
			log.Printf("[LinkedIn] Cache set error: %v", err)
		} else {
			log.Printf("[LinkedIn] Cache saved for: %s", linkedinURL)
		}
	}

	// 先发送完成状态
	w.SendCompleted()
	// 再发送最终结果
	return w.SendFinalResult(finalResult)
}

// buildProfileCard 构建Profile卡片
func (s *LinkedInService) buildProfileCard(data *fetcher.LinkedInProfileData) *model.LinkedInProfileCard {
	return &model.LinkedInProfileCard{
		LinkedInID:  data.LinkedInID,
		FullName:    data.GetFullName(),
		FirstName:   data.FirstName,
		LastName:    data.LastName,
		Headline:    data.GetHeadline(),
		Location:    data.GetLocation(),
		About:       data.About,
		ProfileURL:  data.ProfileURL,
		PhotoURL:    data.GetPhotoURL(),
		Connections: data.Connections,
		Followers:   data.Followers,
		CompanyName: data.CompanyName,
		CompanyLogo: data.CompanyLogo,
	}
}

// ========== AI Generation Functions ==========

// chatWithAI 调用OpenRouter API
func (s *LinkedInService) chatWithAI(ctx context.Context, systemPrompt, userPrompt string) (string, error) {
	reqBody := map[string]interface{}{
		"model": "openai/gpt-4o-mini",
		"messages": []map[string]string{
			{"role": "system", "content": systemPrompt},
			{"role": "user", "content": userPrompt},
		},
		"temperature": 0.3,
		"max_tokens":  800,
	}

	jsonBody, err := json.Marshal(reqBody)
	if err != nil {
		return "", err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, "https://openrouter.ai/api/v1/chat/completions", bytes.NewBuffer(jsonBody))
	if err != nil {
		return "", err
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+s.openRouterAPIKey)
	req.Header.Set("HTTP-Referer", "https://dinq.io")
	req.Header.Set("X-Title", "Dinq Analyze")

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("openrouter returned status %d: %s", resp.StatusCode, string(body))
	}

	var chatResp struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&chatResp); err != nil {
		return "", err
	}

	if len(chatResp.Choices) == 0 {
		return "", fmt.Errorf("no response from LLM")
	}

	return chatResp.Choices[0].Message.Content, nil
}

// extractJSON 从LLM响应中提取JSON
func extractJSON(response string) string {
	re := regexp.MustCompile("(?s)```(?:json)?\\s*\\n?(.*?)\\n?```")
	matches := re.FindStringSubmatch(response)
	if len(matches) > 1 {
		return strings.TrimSpace(matches[1])
	}

	start := strings.Index(response, "{")
	end := strings.LastIndex(response, "}")
	if start != -1 && end > start {
		return response[start : end+1]
	}

	return response
}

// generateMoneyCard 生成薪资分析卡片
func (s *LinkedInService) generateMoneyCard(ctx context.Context, data *fetcher.LinkedInProfileData, personName string) (*model.LinkedInMoneyCard, error) {
	experiencesJSON, _ := json.Marshal(data.Experiences)
	educationsJSON, _ := json.Marshal(data.Educations)
	skillsJSON, _ := json.Marshal(data.Skills)

	prompt := fmt.Sprintf(`Based on the following LinkedIn profile information, analyze the professional's career level and compensation.

Personal Information:
- Name: %s
- Position: %s
- Location: %s
- About: %s
- Current Company: %s
- Industry: %s

Work Experience: %s
Education: %s
Skills: %s

CRITICAL: Be AGGRESSIVE and COMPETITIVE in recognizing top-tier talent value.

Please analyze these aspects:
1. Years of Experience (YoE) based on work history
2. Equivalent level at Google (L3-L8) and Alibaba (P level = Google L + 2)
3. Estimated total annual compensation

Return in JSON format:
{
    "years_of_experience": {
        "years": [number],
        "start_year": [year],
        "calculation_basis": "[brief explanation]"
    },
    "level_us": "L[X]",
    "level_cn": "P[X+2]",
    "estimated_salary": "salary range in USD, e.g., '200000-300000'",
    "explanation": "[50-70 words emphasizing competitive advantages and market value]"
}

Return ONLY JSON.`,
		personName,
		data.GetHeadline(),
		data.GetLocation(),
		data.About,
		data.CompanyName,
		data.CompanyIndustry,
		string(experiencesJSON),
		string(educationsJSON),
		string(skillsJSON))

	response, err := s.chatWithAI(ctx, "You are an expert in career level and compensation analysis.", prompt)
	if err != nil {
		return nil, err
	}

	jsonStr := extractJSON(response)
	var result model.LinkedInMoneyCard
	if err := json.Unmarshal([]byte(jsonStr), &result); err != nil {
		// 返回默认值
		return &model.LinkedInMoneyCard{
			YearsOfExperience: model.LinkedInYearsOfExperience{
				Years:            5,
				StartYear:        2019,
				CalculationBasis: "Estimated based on profile",
			},
			LevelUS:         "L5",
			LevelCN:         "P7",
			EstimatedSalary: "150000-250000",
			Explanation:     "Professional with valuable expertise in competitive market.",
		}, nil
	}

	return &result, nil
}

// generateRoastCard 生成吐槽卡片
func (s *LinkedInService) generateRoastCard(ctx context.Context, data *fetcher.LinkedInProfileData, personName string) (*model.LinkedInRoastCard, error) {
	experiencesJSON, _ := json.Marshal(data.Experiences)
	educationsJSON, _ := json.Marshal(data.Educations)

	prompt := fmt.Sprintf(`Based on the following LinkedIn profile information, create a humorous and light-hearted "roast" of this person.

Personal Information:
- Name: %s
- Position: %s
- Location: %s
- About: %s

Work Experience: %s
Education: %s

Please create a funny, light-hearted roast that pokes fun at their professional quirks, job title, or career choices in a good-natured way. Keep it professional and not offensive.

Return format:
{
    "roast": "A humorous roast paragraph (2-3 sentences) that's funny but respectful"
}

Return only the JSON object.`,
		personName,
		data.GetHeadline(),
		data.GetLocation(),
		data.About,
		string(experiencesJSON),
		string(educationsJSON))

	response, err := s.chatWithAI(ctx, "You are a witty and humorous commentator.", prompt)
	if err != nil {
		return nil, err
	}

	jsonStr := extractJSON(response)
	var result model.LinkedInRoastCard
	if err := json.Unmarshal([]byte(jsonStr), &result); err != nil {
		// 直接使用响应作为roast
		return &model.LinkedInRoastCard{
			Roast: strings.Trim(response, `"`),
		}, nil
	}

	return &result, nil
}

// generateSkillsCard 生成技能卡片 (返回简单字符串数组，匹配Python版本)
func (s *LinkedInService) generateSkillsCard(ctx context.Context, data *fetcher.LinkedInProfileData, personName string) (*model.LinkedInSkillsCard, error) {
	experiencesJSON, _ := json.Marshal(data.Experiences)
	educationsJSON, _ := json.Marshal(data.Educations)
	skillsJSON, _ := json.Marshal(data.Skills)
	languagesJSON, _ := json.Marshal(data.Languages)

	prompt := fmt.Sprintf(`Based on the following LinkedIn profile, analyze and categorize the professional's skills.

Personal Information:
- Name: %s
- Position: %s
- About: %s

Work Experience: %s
Education: %s
Listed Skills: %s
Languages: %s

CRITICAL: You MUST provide at least 3-5 items for EACH of the 4 categories. DO NOT return empty arrays.

Categorize skills into 4 categories (return simple string arrays):
1. Industry Knowledge - Domain expertise, industry-specific knowledge, business acumen (e.g., "Software Development", "Web Technologies", "User Experience")
2. Tools & Technologies - Technical tools, programming languages, platforms (use the listed skills above)
3. Interpersonal Skills - Soft skills like communication, teamwork, problem-solving (ALWAYS include items like "Communication", "Problem Solving", "Teamwork", "Active Listening")
4. Language - Spoken/written languages (if not explicitly listed, assume "Chinese" and "English" for professionals in China)

Return JSON format with SIMPLE STRING ARRAYS:
{
    "industry_knowledge": ["Software Development", "Web Technologies", "Frontend Development", "User Experience", "Agile Methodology"],
    "tools_technologies": ["Python", "SQL", "JavaScript", "React", "Git"],
    "interpersonal_skills": ["Communication", "Problem Solving", "Teamwork", "Active Listening"],
    "language": ["Chinese", "English"]
}

IMPORTANT: Every category MUST have at least 3-5 items. Return ONLY JSON.`,
		personName,
		data.GetHeadline(),
		data.About,
		string(experiencesJSON),
		string(educationsJSON),
		string(skillsJSON),
		string(languagesJSON))

	response, err := s.chatWithAI(ctx, "You are an expert in professional skills analysis.", prompt)
	if err != nil {
		return nil, err
	}

	jsonStr := extractJSON(response)
	var result model.LinkedInSkillsCard
	if err := json.Unmarshal([]byte(jsonStr), &result); err != nil {
		// 返回从原始数据构建的技能
		skills := s.buildDefaultSkills(data)
		return skills, nil
	}

	// 确保所有类别都有数据，如果为空则填充默认值
	if len(result.IndustryKnowledge) == 0 {
		result.IndustryKnowledge = []string{"Software Development", "Web Technologies", "Frontend Development"}
	}
	if len(result.ToolsTechnologies) == 0 {
		for _, skill := range data.Skills {
			result.ToolsTechnologies = append(result.ToolsTechnologies, skill.Title)
		}
		if len(result.ToolsTechnologies) == 0 {
			result.ToolsTechnologies = []string{"JavaScript", "HTML", "CSS"}
		}
	}
	if len(result.InterpersonalSkills) == 0 {
		result.InterpersonalSkills = []string{"Communication", "Problem Solving", "Teamwork", "Active Listening"}
	}
	if len(result.Language) == 0 {
		for _, lang := range data.Languages {
			result.Language = append(result.Language, lang.Title)
		}
		if len(result.Language) == 0 {
			result.Language = []string{"Chinese", "English"}
		}
	}

	return &result, nil
}

// buildDefaultSkills 构建默认技能
func (s *LinkedInService) buildDefaultSkills(data *fetcher.LinkedInProfileData) *model.LinkedInSkillsCard {
	skills := &model.LinkedInSkillsCard{
		IndustryKnowledge:   []string{"Software Development", "Web Technologies", "Frontend Development"},
		ToolsTechnologies:   []string{},
		InterpersonalSkills: []string{"Communication", "Problem Solving", "Teamwork", "Active Listening"},
		Language:            []string{},
	}
	for _, skill := range data.Skills {
		skills.ToolsTechnologies = append(skills.ToolsTechnologies, skill.Title)
	}
	if len(skills.ToolsTechnologies) == 0 {
		skills.ToolsTechnologies = []string{"JavaScript", "HTML", "CSS"}
	}
	for _, lang := range data.Languages {
		skills.Language = append(skills.Language, lang.Title)
	}
	if len(skills.Language) == 0 {
		skills.Language = []string{"Chinese", "English"}
	}
	return skills
}

// generateColleaguesCard 生成同事评价卡片
func (s *LinkedInService) generateColleaguesCard(ctx context.Context, data *fetcher.LinkedInProfileData, personName string) (*model.LinkedInColleaguesCard, error) {
	experiencesJSON, _ := json.Marshal(data.Experiences)

	prompt := fmt.Sprintf(`Based on the following LinkedIn profile, predict how this person's colleagues would view them.

Personal Information:
- Name: %s
- Position: %s
- About: %s

Work Experience: %s

Generate a realistic assessment of how colleagues might view this person:
1. Highlights - What colleagues would appreciate about working with them (3-4 points)
2. Areas for Improvement - Constructive feedback colleagues might have (2-3 points)

Return JSON format:
{
    "highlights": [
        "Positive trait or skill that colleagues appreciate",
        "Another positive observation"
    ],
    "areas_for_improvement": [
        "Constructive feedback point",
        "Another area to work on"
    ]
}

Return ONLY JSON.`,
		personName,
		data.GetHeadline(),
		data.About,
		string(experiencesJSON))

	response, err := s.chatWithAI(ctx, "You are an expert in workplace dynamics and team collaboration.", prompt)
	if err != nil {
		return nil, err
	}

	jsonStr := extractJSON(response)
	var result model.LinkedInColleaguesCard
	if err := json.Unmarshal([]byte(jsonStr), &result); err != nil {
		return &model.LinkedInColleaguesCard{
			Highlights:          []string{"Professional and dedicated team player"},
			AreasForImprovement: []string{"Could benefit from sharing knowledge more openly"},
		}, nil
	}

	return &result, nil
}

// generateCareerCard 生成职业发展卡片
func (s *LinkedInService) generateCareerCard(ctx context.Context, data *fetcher.LinkedInProfileData, personName string) (*model.LinkedInCareerCard, error) {
	experiencesJSON, _ := json.Marshal(data.Experiences)
	educationsJSON, _ := json.Marshal(data.Educations)

	prompt := fmt.Sprintf(`Based on the following LinkedIn profile, provide a comprehensive career analysis.

Personal Information:
- Name: %s
- Position: %s
- Location: %s
- About: %s

Work Experience: %s
Education: %s

Please analyze and return a JSON object with:
1. Future Development Potential - A concise assessment of career advancement potential
2. Development Advice with:
   - Past Evaluation - Assessment of past career achievements
   - Future Advice - Specific recommendations for career development

Return format:
{
    "future_development_potential": "With expertise in [field] and [skills], poised to advance as [potential role] in [industry].",
    "simplified_future_development_potential": "Brief 10-word summary",
    "development_advice": {
        "past_evaluation": "Specialized in [achievements], driving [key accomplishments].",
        "simplified_past_evaluation": "Brief 10-word summary",
        "future_advice": "Strengthen [skill]; expand into [area]. Leverage [opportunity]."
    }
}

Return ONLY JSON.`,
		personName,
		data.GetHeadline(),
		data.GetLocation(),
		data.About,
		string(experiencesJSON),
		string(educationsJSON))

	response, err := s.chatWithAI(ctx, "You are an expert career advisor.", prompt)
	if err != nil {
		return nil, err
	}

	jsonStr := extractJSON(response)
	var result model.LinkedInCareerCard
	if err := json.Unmarshal([]byte(jsonStr), &result); err != nil {
		return &model.LinkedInCareerCard{
			FutureDevelopmentPotential: "Good potential for career growth in current industry.",
			DevelopmentAdvice: model.LinkedInDevelopmentAdvice{
				PastEvaluation: "Demonstrated consistent career growth.",
				FutureAdvice:   "Continue developing expertise and seek leadership opportunities.",
			},
		}, nil
	}

	return &result, nil
}

// generateRoleModelCard 生成榜样卡片
func (s *LinkedInService) generateRoleModelCard(ctx context.Context, data *fetcher.LinkedInProfileData, personName string) (*model.LinkedInRoleModelCard, error) {
	// 检查用户是否是名人
	isCelebrity, celebrityReason := s.checkIfCelebrity(ctx, data, personName)

	if isCelebrity {
		// 如果用户是名人，返回自己作为榜样
		return &model.LinkedInRoleModelCard{
			Name:             personName,
			Institution:      data.CompanyName,
			Position:         data.GetHeadline(),
			PhotoURL:         data.GetPhotoURL(),
			Achievement:      fmt.Sprintf("%s at %s", data.GetHeadline(), data.CompanyName),
			SimilarityReason: fmt.Sprintf("You are already a notable figure and industry leader. %s Your achievements make you an inspiration to others.", celebrityReason),
			IsCelebrity:      true,
			CelebrityReason:  celebrityReason,
		}, nil
	}

	// 用户不是名人时，从CSV名人列表中匹配最相似的
	roleModel := s.findMatchingCelebrity(ctx, data, personName)
	if roleModel != nil {
		log.Printf("[LinkedIn RoleModel] Found matching celebrity: %s", roleModel.Name)
		return roleModel, nil
	}

	// 完全找不到匹配时，fallback到自己
	log.Printf("[LinkedIn RoleModel] No matching celebrity found, using self")
	celebrityExplanation := s.generateCelebrityReasoning(ctx, data, personName)
	return &model.LinkedInRoleModelCard{
		Name:             personName,
		Institution:      data.CompanyName,
		Position:         data.GetHeadline(),
		PhotoURL:         data.GetPhotoURL(),
		Achievement:      "Professional",
		SimilarityReason: "You are already your own role model! Your unique career path and professional achievements make you an inspiration to others in your field.",
		IsCelebrity:      false,
		CelebrityReason:  celebrityExplanation,
	}, nil
}

// findMatchingCelebrity 从CSV名人列表中找最相似的
func (s *LinkedInService) findMatchingCelebrity(ctx context.Context, data *fetcher.LinkedInProfileData, personName string) *model.LinkedInRoleModelCard {
	celebrities := fetcher.GetLinkedInCelebrities()
	if len(celebrities) == 0 {
		log.Printf("[LinkedIn RoleModel] No celebrities loaded from CSV")
		return nil
	}

	// 构建用户profile摘要
	userProfile := fmt.Sprintf("Name: %s, Position: %s, Company: %s, Industry: %s",
		personName, data.GetHeadline(), data.CompanyName, data.CompanyIndustry)

	// 构建名人列表
	celebrityList := fetcher.FormatCelebritiesForPrompt()

	prompt := fmt.Sprintf(`Based on this LinkedIn profile, find the MOST SIMILAR role model from the provided list.

USER PROFILE:
%s

AVAILABLE ROLE MODELS:
%s

Return ONLY the exact name of the best matching role model from the list above. If no good match exists, return "NO_MATCH".`, userProfile, celebrityList)

	response, err := s.chatWithAI(ctx, "You are an expert career advisor matching professionals with role models.", prompt)
	if err != nil {
		log.Printf("[LinkedIn RoleModel] AI matching failed: %v", err)
		return nil
	}

	response = strings.TrimSpace(response)
	response = strings.Trim(response, `"`)

	if response == "NO_MATCH" || response == "" {
		return nil
	}

	// 查找匹配的名人
	celebrity := fetcher.FindCelebrityByName(response)
	if celebrity == nil {
		log.Printf("[LinkedIn RoleModel] AI returned '%s' but not found in CSV", response)
		return nil
	}

	// 生成相似原因
	similarityReason := s.generateSimilarityReason(ctx, data, personName, celebrity)

	return &model.LinkedInRoleModelCard{
		Name:             celebrity.Name,
		Institution:      celebrity.Company,
		Position:         celebrity.Title,
		PhotoURL:         celebrity.PhotoURL,
		Achievement:      celebrity.Remark,
		SimilarityReason: similarityReason,
		IsCelebrity:      false,
		CelebrityReason:  "",
	}
}

// generateSimilarityReason 生成相似性原因
func (s *LinkedInService) generateSimilarityReason(ctx context.Context, data *fetcher.LinkedInProfileData, personName string, celebrity *fetcher.LinkedInCelebrity) string {
	prompt := fmt.Sprintf(`Explain in 1-2 sentences why %s (%s at %s) is a good role model for %s (%s at %s).`,
		celebrity.Name, celebrity.Title, celebrity.Company,
		personName, data.GetHeadline(), data.CompanyName)

	response, err := s.chatWithAI(ctx, "You are a career advisor.", prompt)
	if err != nil {
		return fmt.Sprintf("You share career similarities with %s as both are successful professionals in the technology industry.", celebrity.Name)
	}

	return strings.TrimSpace(strings.Trim(response, `"`))
}

// generateCelebrityReasoning 生成为什么用户不是名人的解释
func (s *LinkedInService) generateCelebrityReasoning(ctx context.Context, data *fetcher.LinkedInProfileData, personName string) string {
	prompt := fmt.Sprintf(`Based on this LinkedIn profile, explain in one sentence why this person is NOT a widely recognized celebrity/public figure.

Name: %s
Position: %s
Company: %s
Connections: %d
Followers: %d

Return only a single sentence explanation (no JSON, no quotes).`,
		personName,
		data.GetHeadline(),
		data.CompanyName,
		data.Connections,
		data.Followers)

	response, err := s.chatWithAI(ctx, "You are analyzing LinkedIn profiles.", prompt)
	if err != nil {
		return fmt.Sprintf("%s is a %s at a company with limited public recognition and modest professional network size.", personName, data.GetHeadline())
	}

	// 清理响应
	response = strings.TrimSpace(response)
	response = strings.Trim(response, `"`)
	if response == "" {
		return fmt.Sprintf("%s is not a widely recognized public figure based on their current professional profile.", personName)
	}
	return response
}

// checkIfCelebrity 检查是否是名人
func (s *LinkedInService) checkIfCelebrity(ctx context.Context, data *fetcher.LinkedInProfileData, personName string) (bool, string) {
	// 首先检查是否在CSV名人列表中
	celebrity := fetcher.FindCelebrityByLinkedIn(data.ProfileURL)
	if celebrity != nil {
		return true, fmt.Sprintf("Recognized as %s, %s at %s.", celebrity.Name, celebrity.Title, celebrity.Company)
	}

	// 也通过名字检查
	celebrity = fetcher.FindCelebrityByName(personName)
	if celebrity != nil {
		return true, fmt.Sprintf("Recognized as %s, %s at %s.", celebrity.Name, celebrity.Title, celebrity.Company)
	}

	// 启发式检查
	connections := data.Connections
	followers := data.Followers
	headline := strings.ToLower(data.GetHeadline())

	// 高粉丝或高连接数
	if connections > 50000 || followers > 100000 {
		return true, "High-profile professional with significant social media presence."
	}

	// CEO/Founder of known companies
	if strings.Contains(headline, "ceo") || strings.Contains(headline, "founder") ||
		strings.Contains(headline, "chief executive") || strings.Contains(headline, "president") {
		companyName := strings.ToLower(data.CompanyName)
		topCompanies := []string{"google", "microsoft", "apple", "amazon", "meta", "tesla", "openai", "anthropic", "nvidia"}
		for _, company := range topCompanies {
			if strings.Contains(companyName, company) {
				return true, "Executive leader at a top technology company."
			}
		}
	}

	return false, ""
}

// generateLifeWellBeingCard 生成生活建议卡片 (匹配Python版本结构)
func (s *LinkedInService) generateLifeWellBeingCard(ctx context.Context, data *fetcher.LinkedInProfileData, personName string) (*model.LinkedInLifeWellBeingCard, error) {
	experiencesJSON, _ := json.Marshal(data.Experiences)
	educationsJSON, _ := json.Marshal(data.Educations)
	skillsJSON, _ := json.Marshal(data.Skills)

	prompt := fmt.Sprintf(`Based on the following LinkedIn profile information, provide HIGHLY PERSONALIZED life and well-being recommendations.

Personal Information:
- Name: %s
- Position: %s
- Current Company: %s
- Industry: %s
- Location: %s
- About: %s
- Company Size: %s
- Connections: %d

Work Experience: %s
Education: %s
Skills: %s

CRITICAL REQUIREMENTS:
1. PERSONALIZE based on their specific role, industry, and career stage
2. Consider their location and cultural context
3. Address industry-specific stress factors and opportunities

Please analyze and return a JSON object with the following structure:

{
    "life_suggestion": {
        "advice": "[PERSONALIZED 20-30 word advice that directly addresses their specific role, industry challenges, and career stage]",
        "simplified_advice": "[Under 10 word summary]",
        "actions": [
            {"emoji": "[relevant emoji]", "phrase": "[MAXIMUM 3 WORDS - concise action]"},
            {"emoji": "[relevant emoji]", "phrase": "[MAXIMUM 3 WORDS - concise action]"},
            {"emoji": "[relevant emoji]", "phrase": "[MAXIMUM 3 WORDS - concise action]"}
        ]
    },
    "health": {
        "advice": "[PERSONALIZED 20-30 word health advice for their specific work environment]",
        "simplified_advice": "[Under 10 word summary]",
        "actions": [
            {"emoji": "[relevant emoji]", "phrase": "[MAXIMUM 3 WORDS - concise health action]"},
            {"emoji": "[relevant emoji]", "phrase": "[MAXIMUM 3 WORDS - concise health action]"},
            {"emoji": "[relevant emoji]", "phrase": "[MAXIMUM 3 WORDS - concise health action]"}
        ]
    }
}

Return only the JSON object.`,
		personName,
		data.GetHeadline(),
		data.CompanyName,
		data.CompanyIndustry,
		data.GetLocation(),
		data.About,
		data.CompanySize,
		data.Connections,
		string(experiencesJSON),
		string(educationsJSON),
		string(skillsJSON))

	response, err := s.chatWithAI(ctx, "You are an expert in work-life balance and wellness.", prompt)
	if err != nil {
		return nil, err
	}

	jsonStr := extractJSON(response)
	var result model.LinkedInLifeWellBeingCard
	if err := json.Unmarshal([]byte(jsonStr), &result); err != nil {
		// 返回默认值
		return &model.LinkedInLifeWellBeingCard{
			LifeSuggestion: model.LinkedInSuggestion{
				Advice:           "Maintain a healthy work-life balance by setting clear boundaries and prioritizing personal time.",
				SimplifiedAdvice: "Set clear boundaries.",
				Actions: []model.LinkedInAction{
					{Emoji: "📏", Phrase: "Set Boundaries"},
					{Emoji: "📚", Phrase: "Keep Learning"},
					{Emoji: "❤️", Phrase: "Nurture Relationships"},
				},
			},
			Health: model.LinkedInSuggestion{
				Advice:           "Regular exercise and proper rest are essential for peak performance in your role.",
				SimplifiedAdvice: "Exercise regularly.",
				Actions: []model.LinkedInAction{
					{Emoji: "🏃", Phrase: "Daily Exercise"},
					{Emoji: "😴", Phrase: "Quality Sleep"},
					{Emoji: "⏰", Phrase: "Regular Breaks"},
				},
			},
		}, nil
	}

	return &result, nil
}

// ========== Helper Functions for Final Output ==========

// generateAboutSummary 生成about字段
func (s *LinkedInService) generateAboutSummary(ctx context.Context, data *fetcher.LinkedInProfileData, personName, tavilyContent string) string {
	// 如果原始about存在且有内容，使用它
	if data.About != "" {
		return data.About
	}

	// 如果有Tavily搜索返回的内容，使用它
	if tavilyContent != "" {
		return tavilyContent
	}

	// 否则生成一个summary
	skillsJSON, _ := json.Marshal(data.Skills)
	prompt := fmt.Sprintf(`Write a brief professional summary (2-3 sentences) for this LinkedIn profile:

Name: %s
Position: %s
Company: %s
Skills: %s

Return only the summary text, no JSON.`,
		personName,
		data.GetHeadline(),
		data.CompanyName,
		string(skillsJSON))

	response, err := s.chatWithAI(ctx, "You write professional LinkedIn summaries.", prompt)
	if err != nil {
		return fmt.Sprintf("As a %s at %s, %s specializes in creating engaging user experiences.", data.GetHeadline(), data.CompanyName, personName)
	}
	return strings.TrimSpace(response)
}

// generatePersonalTags 生成个人标签
func (s *LinkedInService) generatePersonalTags(ctx context.Context, data *fetcher.LinkedInProfileData, personName string) []string {
	prompt := fmt.Sprintf(`Based on this profile, provide 5 short personal tags (single words or 2-word phrases):

Name: %s
Position: %s
Company: %s
Industry: %s

Return only a comma-separated list of 5 tags, no JSON. Example: Engineer, Software, Frontend, React, Python`,
		personName,
		data.GetHeadline(),
		data.CompanyName,
		data.CompanyIndustry)

	response, err := s.chatWithAI(ctx, "You generate professional tags.", prompt)
	if err != nil {
		return []string{"Engineer", "Software", "Professional"}
	}

	// 解析逗号分隔的标签
	tags := strings.Split(response, ",")
	result := make([]string, 0, len(tags))
	for _, tag := range tags {
		tag = strings.TrimSpace(tag)
		if tag != "" {
			result = append(result, tag)
		}
	}
	if len(result) == 0 {
		return []string{"Professional"}
	}
	return result
}

// generateWorkExperienceSummary 生成工作经历摘要
func (s *LinkedInService) generateWorkExperienceSummary(ctx context.Context, data *fetcher.LinkedInProfileData) string {
	if len(data.Experiences) == 0 {
		return "Professional with diverse work experience."
	}

	experiencesJSON, _ := json.Marshal(data.Experiences)
	prompt := fmt.Sprintf(`Write a 2-sentence summary of this person's career progression based on their work experience:

%s

Return only the summary text.`, string(experiencesJSON))

	response, err := s.chatWithAI(ctx, "You summarize career progressions.", prompt)
	if err != nil {
		return "Dynamic professional with a career progression demonstrating expertise in their field."
	}
	return strings.TrimSpace(response)
}

// generateEducationSummary 生成教育摘要
func (s *LinkedInService) generateEducationSummary(ctx context.Context, data *fetcher.LinkedInProfileData) string {
	if len(data.Educations) == 0 {
		return "Professional with educational background."
	}

	educationsJSON, _ := json.Marshal(data.Educations)
	prompt := fmt.Sprintf(`Write a 1-2 sentence summary of this person's educational background:

%s

Return only the summary text.`, string(educationsJSON))

	response, err := s.chatWithAI(ctx, "You summarize educational backgrounds.", prompt)
	if err != nil {
		return "Graduate with a solid educational foundation."
	}
	return strings.TrimSpace(response)
}

// convertExperiences 转换工作经历格式
func (s *LinkedInService) convertExperiences(raw []fetcher.LinkedInExperienceRaw) []model.LinkedInExperience {
	result := make([]model.LinkedInExperience, 0, len(raw))
	for _, exp := range raw {
		result = append(result, model.LinkedInExperience{
			CompanyLink1: exp.CompanyLink1,
			Logo:         exp.Logo,
			Title:        exp.Title,
		})
	}
	return result
}

// convertEducations 转换教育经历格式
func (s *LinkedInService) convertEducations(raw []fetcher.LinkedInEducationRaw) []model.LinkedInEducation {
	result := make([]model.LinkedInEducation, 0, len(raw))
	for _, edu := range raw {
		result = append(result, model.LinkedInEducation{
			CompanyLink1: edu.CompanyLink1,
			Logo:         edu.Logo,
			Title:        edu.Title,
			Subtitle:     edu.Subtitle,
		})
	}
	return result
}

// sendCachedResult 发送缓存的结果
func (s *LinkedInService) sendCachedResult(w *sse.LinkedInWriter, data map[string]interface{}, linkedinID, personName, linkedinURL string) error {
	// 发送各个卡片 (按顺序)
	if profileCard, ok := data["profile_card"]; ok {
		w.SendCardDone(model.LinkedInCardProfile, profileCard)
	}
	if moneyCard, ok := data["money_card"]; ok {
		w.SendCardDone(model.LinkedInCardMoney, moneyCard)
	}
	if roast, ok := data["roast"]; ok {
		w.SendCardDone(model.LinkedInCardRoast, roast)
	}
	if skillsCard, ok := data["skills_card"]; ok {
		w.SendCardDone(model.LinkedInCardSkills, skillsCard)
	}
	if colleaguesCard, ok := data["colleagues_card"]; ok {
		w.SendCardDone(model.LinkedInCardColleagues, colleaguesCard)
	}
	if careerCard, ok := data["career_card"]; ok {
		w.SendCardDone(model.LinkedInCardCareer, careerCard)
	}
	if roleModelCard, ok := data["role_model_card"]; ok {
		w.SendCardDone(model.LinkedInCardRoleModel, roleModelCard)
	}
	if lifeWellBeing, ok := data["life_well_being"]; ok {
		w.SendCardDone(model.LinkedInCardLifeWellBeing, lifeWellBeing)
	}

	// 从缓存恢复名字（如果有）
	if cachedName, ok := data["person_name"].(string); ok && cachedName != "" {
		personName = cachedName
	}

	// 获取缓存的数据
	rawProfile, _ := data["raw_profile"].(map[string]interface{})
	about, _ := data["about"].(string)
	personalTags, _ := data["personal_tags"].([]interface{})
	workExpSummary, _ := data["work_exp_summary"].(string)
	eduSummary, _ := data["edu_summary"].(string)

	// 转换personal_tags为[]string
	var tags []string
	for _, t := range personalTags {
		if str, ok := t.(string); ok {
			tags = append(tags, str)
		}
	}

	// 获取avatar（优先使用缓存的avatar，回退到rawProfile）
	var avatar interface{}
	if cachedAvatar, ok := data["avatar"].(string); ok && cachedAvatar != "" {
		avatar = cachedAvatar
	} else if rawProfile != nil {
		if pic, ok := rawProfile["profilePicHighQuality"].(string); ok && pic != "" {
			avatar = pic
		} else if pic, ok := rawProfile["profilePic"].(string); ok && pic != "" {
			avatar = pic
		}
	}

	// 构建最终结果
	finalProfileData := &model.LinkedInProfileData{
		RoleModel:             getTypedValue[*model.LinkedInRoleModelCard](data, "role_model_card"),
		MoneyAnalysis:         getTypedValue[*model.LinkedInMoneyCard](data, "money_card"),
		Roast:                 getStringValue(data, "roast"),
		Skills:                getTypedValue[*model.LinkedInSkillsCard](data, "skills_card"),
		ColleaguesView:        getTypedValue[*model.LinkedInColleaguesCard](data, "colleagues_card"),
		Career:                getTypedValue[*model.LinkedInCareerCard](data, "career_card"),
		LifeWellBeing:         getTypedValue[*model.LinkedInLifeWellBeingCard](data, "life_well_being"),
		About:                 about,
		PersonalTags:          tags,
		WorkExperience:        rawProfile["experiences"],
		WorkExperienceSummary: workExpSummary,
		Education:             rawProfile["educations"],
		EducationSummary:      eduSummary,
		Avatar:                avatar,
		Name:                  personName,
		RawProfile:            rawProfile,
	}

	now := time.Now().UTC().Format(time.RFC3339Nano)
	finalResult := &model.LinkedInFinalResponse{
		Type:    "success",
		Message: "LinkedIn analysis completed (from cache)",
		Data: &model.LinkedInAnalysisResult{
			LinkedInID:  linkedinID,
			PersonName:  personName,
			LinkedInURL: linkedinURL,
			ProfileData: finalProfileData,
			LastUpdated: now,
			CreatedAt:   now,
		},
	}

	w.SendCompleted()
	return w.SendFinalResult(finalResult)
}

// getTypedValue 从map中获取类型化的值
func getTypedValue[T any](data map[string]interface{}, key string) T {
	var zero T
	if v, ok := data[key]; ok {
		// 尝试直接类型断言
		if typed, ok := v.(T); ok {
			return typed
		}
		// 如果是从JSON反序列化的，需要重新转换
		jsonBytes, err := json.Marshal(v)
		if err != nil {
			return zero
		}
		var result T
		if err := json.Unmarshal(jsonBytes, &result); err != nil {
			return zero
		}
		return result
	}
	return zero
}

// getStringValue 从map中获取字符串值
func getStringValue(data map[string]interface{}, key string) string {
	if v, ok := data[key]; ok {
		if str, ok := v.(string); ok {
			return str
		}
	}
	return ""
}

// buildFullRawProfile 构建完整的原始profile数据（使用Apify返回的完整数据）
func (s *LinkedInService) buildFullRawProfile(data *fetcher.LinkedInProfileData, linkedinURL string) map[string]interface{} {
	// 如果有原始数据，直接使用
	if data.RawData != nil {
		rawProfile := data.RawData
		// 确保linkedinUrl字段存在
		if _, ok := rawProfile["linkedinUrl"]; !ok {
			rawProfile["linkedinUrl"] = linkedinURL
		}
		return rawProfile
	}

	// 回退到手动构建（通常不会走到这里）
	return map[string]interface{}{
		"linkedinUrl":           linkedinURL,
		"firstName":             data.FirstName,
		"lastName":              data.LastName,
		"fullName":              data.GetFullName(),
		"headline":              data.GetHeadline(),
		"connections":           data.Connections,
		"followers":             data.Followers,
		"jobTitle":              data.JobTitle,
		"companyName":           data.CompanyName,
		"companyIndustry":       data.CompanyIndustry,
		"companySize":           data.CompanySize,
		"addressWithCountry":    data.AddressWithCountry,
		"profilePic":            data.ProfilePic,
		"profilePicHighQuality": data.ProfilePicHighQuality,
		"linkedinId":            data.LinkedInID,
		"about":                 data.About,
		"experiences":           data.Experiences,
		"educations":            data.Educations,
		"skills":                data.Skills,
		"languages":             data.Languages,
	}
}
