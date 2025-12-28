# 开发先驱API文档

## 📋 概述

开发先驱API提供访问全球知名开发者和技术先驱数据的功能。该API包含了来自各个技术领域的杰出开发者信息，包括他们的GitHub链接、技术专长、著名作品、公司信息等。

## 🎯 API端点

### GET `/api/github/dev-pioneers`

**描述**: 获取开发先驱数据，支持多种过滤和排序选项

**认证**: ❌ 不需要认证

**Content-Type**: `application/json`

---

## 📤 请求参数

所有参数都是可选的查询参数：

| 参数 | 类型 | 默认值 | 描述 | 示例 |
|------|------|--------|------|------|
| `count` | integer | 10 | 返回的数量 (1-50) | `?count=20` |
| `random` | boolean | false | 是否随机选择 | `?random=true` |
| `area` | string | - | 按技术领域过滤 | `?area=AI` |
| `company` | string | - | 按公司过滤 | `?company=Google` |

### 请求示例

```http
GET /api/github/dev-pioneers?count=5&random=true HTTP/1.1
Host: localhost:5001
Accept: application/json
```

---

## 📥 响应格式

### 成功响应 (200 OK)

```json
{
  "success": true,
  "count": 5,
  "total_available": 45,
  "total_in_database": 122,
  "pioneers": [
    {
      "name": "Linus Torvalds",
      "github": "https://github.com/torvalds",
      "area": "Operating System",
      "personal_page": "",
      "twitter": "https://twitter.com/Linus__Torvalds",
      "linkedin": "",
      "image": "https://pbs.twimg.com/profile_images/2828597835/0f1840e9c2fbafa93fe6f0d7ccf64a3e_400x400.jpeg",
      "famous_work": "Linux",
      "link": "https://github.com/torvalds/linux",
      "Company": "Linux Foundation",
      "Job": "Founder",
      "has_github": true,
      "has_personal_page": false,
      "has_twitter": true,
      "has_linkedin": false,
      "has_image": true
    }
  ],
  "filters_applied": {
    "area": null,
    "company": null,
    "random_selection": true
  },
  "metadata": {
    "available_areas": [
      "AI Agent",
      "AI App", 
      "AI Infra",
      "AI Tooling",
      "AIGC",
      "Audio",
      "Backend",
      "Blockchain & Video Game",
      "C++",
      "Cloud Computing",
      "Compiler",
      "Computer Vision",
      "Database",
      "Deep Learning",
      "Deep Learning Framework",
      "Distributed System",
      "Distributed Systems and Parallel Computing",
      "Distributed Systems and Web Search",
      "Frontend",
      "Full-stack",
      "GNN",
      "Go",
      "Graphics",
      "Java",
      "LLM",
      "LLMSys",
      "Large-Scale Data Processing",
      "Large scale Machine Learning",
      "ML Architecture",
      "Machine Learning",
      "NLP",
      "Network",
      "Operating System",
      "Programming Language",
      "Python",
      "Reinforcement Learning",
      "Server",
      "System",
      "TTS",
      "Text Editor",
      "TypeScript",
      "User Experience",
      "Visualization",
      "Web",
      "machine learning compilers and runtimes"
    ],
    "available_companies": [
      "37Signals",
      "AnyScale",
      "AutoGen",
      "AutoGPT",
      "Bluesky",
      "Brave",
      "Browser Use",
      "Carnegie Mellon University",
      "Clerk",
      "Columbia University",
      "ComfyUI",
      "CrewAI",
      "Deno",
      "Docker",
      "Elastic",
      "ElevenLabs",
      "Eliza Labs",
      "EurekaLabs",
      "F5 Networks",
      "Firecrawl",
      "Gitbook",
      "Google",
      "Huggingface",
      "Infiniflow",
      "JetBrains",
      "KCL",
      "Kumo.AI",
      "LangChain",
      "Lepton AI",
      "Lightning AI",
      "Line",
      "Linux Foundation",
      "Manus",
      "Mercedes-Benz",
      "Mermaid Chart",
      "Meshy",
      "Meta",
      "Microsoft",
      "Mistral AI",
      "Modular AI",
      "Moonshot AI",
      "Myshell",
      "Nanyang Technological University",
      "OpenAI",
      "OpenCV Open source Foundation",
      "Oscilar",
      "Pierre",
      "PingCAP",
      "Posit",
      "Prem AI",
      "Quansight",
      "Redis Lab",
      "Reworkd",
      "SEEK",
      "Sakana AI",
      "Sentry",
      "Shanghai AI Laboratory",
      "Snowflake",
      "Soundslice",
      "Supabase",
      "TabbyML",
      "Thinking Machines Lab",
      "Tsinghua University",
      "Turquoise Health",
      "UC Berkeley",
      "Ultralytics",
      "VoidZero",
      "WASEDA University",
      "Vercel",
      "Web3 Company",
      "Workbrew",
      "answer.ai",
      "ndea",
      "xAI",
      "zytedata"
    ],
    "csv_file_path": "/path/to/dev_pioneers.csv"
  }
}
```

### 错误响应 (500 Internal Server Error)

```json
{
  "success": false,
  "error": "Failed to retrieve dev pioneers data",
  "message": "获取开发先驱数据时发生错误"
}
```

---

## 🔍 数据字段说明

### 开发先驱对象字段

| 字段 | 类型 | 描述 | 示例 |
|------|------|------|------|
| `name` | string | 开发者姓名 | "Linus Torvalds" |
| `github` | string | GitHub主页链接 | "https://github.com/torvalds" |
| `area` | string | 技术专长领域 | "Operating System" |
| `personal_page` | string | 个人网站 | "https://example.com" |
| `twitter` | string | Twitter链接 | "https://twitter.com/username" |
| `linkedin` | string | LinkedIn链接 | "https://linkedin.com/in/username" |
| `image` | string | 头像图片链接 | "https://example.com/avatar.jpg" |
| `famous_work` | string | 著名作品/项目 | "Linux" |
| `link` | string | 著名作品链接 | "https://github.com/torvalds/linux" |
| `Company` | string | 当前公司 | "Linux Foundation" |
| `Job` | string | 职位 | "Founder" |

### 计算字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `has_github` | boolean | 是否有GitHub链接 |
| `has_personal_page` | boolean | 是否有个人网站 |
| `has_twitter` | boolean | 是否有Twitter链接 |
| `has_linkedin` | boolean | 是否有LinkedIn链接 |
| `has_image` | boolean | 是否有头像图片 |

---

## 📊 使用示例

### 1. 获取默认数据

```bash
curl "http://localhost:5001/api/github/dev-pioneers"
```

### 2. 获取随机20个开发先驱

```bash
curl "http://localhost:5001/api/github/dev-pioneers?count=20&random=true"
```

### 3. 按技术领域过滤

```bash
# 获取AI相关的开发先驱
curl "http://localhost:5001/api/github/dev-pioneers?area=AI&count=15"

# 获取前端开发先驱
curl "http://localhost:5001/api/github/dev-pioneers?area=Frontend"

# 获取深度学习专家
curl "http://localhost:5001/api/github/dev-pioneers?area=Deep%20Learning"
```

### 4. 按公司过滤

```bash
# 获取Google的开发先驱
curl "http://localhost:5001/api/github/dev-pioneers?company=Google"

# 获取Meta的开发先驱
curl "http://localhost:5001/api/github/dev-pioneers?company=Meta"
```

### 5. 组合过滤

```bash
# 获取Google的AI专家
curl "http://localhost:5001/api/github/dev-pioneers?company=Google&area=AI&count=5"
```

---

## 💻 前端集成示例

### JavaScript/Fetch

```javascript
async function getDevPioneers(options = {}) {
  const {
    count = 10,
    random = false,
    area = '',
    company = ''
  } = options;

  const params = new URLSearchParams();
  if (count !== 10) params.append('count', count);
  if (random) params.append('random', 'true');
  if (area) params.append('area', area);
  if (company) params.append('company', company);

  try {
    const response = await fetch(`/api/github/dev-pioneers?${params}`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    
    if (data.success) {
      return data;
    } else {
      throw new Error(data.message || 'Failed to fetch dev pioneers');
    }
  } catch (error) {
    console.error('Error fetching dev pioneers:', error);
    throw error;
  }
}

// 使用示例
async function displayPioneers() {
  try {
    // 获取随机的AI专家
    const aiExperts = await getDevPioneers({
      area: 'AI',
      count: 8,
      random: true
    });
    
    console.log(`找到 ${aiExperts.count} 个AI专家`);
    aiExperts.pioneers.forEach(pioneer => {
      console.log(`${pioneer.name} - ${pioneer.Company} - ${pioneer.famous_work}`);
    });
    
    // 获取前端开发者
    const frontendDevs = await getDevPioneers({
      area: 'Frontend',
      count: 5
    });
    
    console.log(`找到 ${frontendDevs.count} 个前端开发者`);
    
  } catch (error) {
    console.error('获取开发先驱数据失败:', error);
  }
}
```

### React Hook

```jsx
import { useState, useEffect } from 'react';

function useDevPioneers(options = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchPioneers = async (newOptions = {}) => {
    setLoading(true);
    setError(null);
    
    try {
      const finalOptions = { ...options, ...newOptions };
      const result = await getDevPioneers(finalOptions);
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPioneers();
  }, []);

  return {
    data,
    loading,
    error,
    refetch: fetchPioneers
  };
}

// 使用示例
function DevPioneersComponent() {
  const { data, loading, error, refetch } = useDevPioneers({
    count: 12,
    random: true
  });

  const handleFilterByArea = (area) => {
    refetch({ area, count: 10 });
  };

  if (loading) return <div>加载中...</div>;
  if (error) return <div>错误: {error}</div>;
  if (!data) return <div>暂无数据</div>;

  return (
    <div>
      <h2>开发先驱 ({data.count}/{data.total_in_database})</h2>
      
      {/* 技术领域过滤器 */}
      <div>
        <h3>按技术领域过滤:</h3>
        {data.metadata.available_areas.slice(0, 10).map(area => (
          <button 
            key={area} 
            onClick={() => handleFilterByArea(area)}
          >
            {area}
          </button>
        ))}
      </div>

      {/* 开发先驱列表 */}
      <div className="pioneers-grid">
        {data.pioneers.map((pioneer, index) => (
          <div key={index} className="pioneer-card">
            {pioneer.has_image && (
              <img src={pioneer.image} alt={pioneer.name} />
            )}
            <h3>{pioneer.name}</h3>
            <p><strong>领域:</strong> {pioneer.area}</p>
            <p><strong>公司:</strong> {pioneer.Company}</p>
            <p><strong>职位:</strong> {pioneer.Job}</p>
            <p><strong>著名作品:</strong> {pioneer.famous_work}</p>
            
            <div className="links">
              {pioneer.has_github && (
                <a href={pioneer.github} target="_blank" rel="noopener noreferrer">
                  GitHub
                </a>
              )}
              {pioneer.has_twitter && (
                <a href={pioneer.twitter} target="_blank" rel="noopener noreferrer">
                  Twitter
                </a>
              )}
              {pioneer.has_linkedin && (
                <a href={pioneer.linkedin} target="_blank" rel="noopener noreferrer">
                  LinkedIn
                </a>
              )}
              {pioneer.has_personal_page && (
                <a href={pioneer.personal_page} target="_blank" rel="noopener noreferrer">
                  个人网站
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

### Vue.js 示例

```vue
<template>
  <div class="dev-pioneers">
    <h2>开发先驱</h2>
    
    <!-- 过滤器 -->
    <div class="filters">
      <select v-model="selectedArea" @change="fetchPioneers">
        <option value="">所有技术领域</option>
        <option v-for="area in availableAreas" :key="area" :value="area">
          {{ area }}
        </option>
      </select>
      
      <select v-model="selectedCompany" @change="fetchPioneers">
        <option value="">所有公司</option>
        <option v-for="company in availableCompanies" :key="company" :value="company">
          {{ company }}
        </option>
      </select>
      
      <label>
        <input type="checkbox" v-model="randomSelection" @change="fetchPioneers">
        随机选择
      </label>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading">加载中...</div>
    
    <!-- 错误状态 -->
    <div v-if="error" class="error">{{ error }}</div>
    
    <!-- 开发先驱列表 -->
    <div v-if="pioneers.length" class="pioneers-grid">
      <div v-for="pioneer in pioneers" :key="pioneer.name" class="pioneer-card">
        <img v-if="pioneer.has_image" :src="pioneer.image" :alt="pioneer.name">
        <h3>{{ pioneer.name }}</h3>
        <p><strong>领域:</strong> {{ pioneer.area }}</p>
        <p><strong>公司:</strong> {{ pioneer.Company }}</p>
        <p><strong>著名作品:</strong> {{ pioneer.famous_work }}</p>
        
        <div class="links">
          <a v-if="pioneer.has_github" :href="pioneer.github" target="_blank">GitHub</a>
          <a v-if="pioneer.has_twitter" :href="pioneer.twitter" target="_blank">Twitter</a>
          <a v-if="pioneer.has_linkedin" :href="pioneer.linkedin" target="_blank">LinkedIn</a>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'DevPioneers',
  data() {
    return {
      pioneers: [],
      availableAreas: [],
      availableCompanies: [],
      selectedArea: '',
      selectedCompany: '',
      randomSelection: false,
      loading: false,
      error: null
    };
  },
  
  async mounted() {
    await this.fetchPioneers();
  },
  
  methods: {
    async fetchPioneers() {
      this.loading = true;
      this.error = null;
      
      try {
        const params = new URLSearchParams();
        if (this.selectedArea) params.append('area', this.selectedArea);
        if (this.selectedCompany) params.append('company', this.selectedCompany);
        if (this.randomSelection) params.append('random', 'true');
        params.append('count', '20');
        
        const response = await fetch(`/api/github/dev-pioneers?${params}`);
        const data = await response.json();
        
        if (data.success) {
          this.pioneers = data.pioneers;
          this.availableAreas = data.metadata.available_areas;
          this.availableCompanies = data.metadata.available_companies;
        } else {
          this.error = data.message;
        }
      } catch (err) {
        this.error = '获取数据失败: ' + err.message;
      } finally {
        this.loading = false;
      }
    }
  }
};
</script>
```

---

## 📈 数据统计

### 技术领域分布

当前数据库包含以下技术领域的开发先驱：

- **AI相关** (AI Agent, AI App, AI Infra, AIGC, Deep Learning, LLM, Machine Learning): ~35%
- **前端开发** (Frontend, TypeScript, User Experience): ~15%
- **系统编程** (Operating System, Distributed Systems, Database): ~20%
- **编程语言** (Programming Language, Compiler, Python, Go): ~15%
- **其他专业领域** (Computer Vision, Audio, Graphics, Blockchain等): ~15%

### 公司分布

主要公司包括：
- **大型科技公司**: Google, Meta, Microsoft, OpenAI
- **AI初创公司**: Mistral AI, Anthropic, xAI
- **开源组织**: Linux Foundation, Apache Foundation
- **学术机构**: UC Berkeley, Stanford, Tsinghua University

---

## 🔧 高级用法

### 1. 构建技术专家推荐系统

```javascript
class TechExpertRecommender {
  constructor() {
    this.cache = new Map();
  }

  async getExpertsByTech(technology) {
    if (this.cache.has(technology)) {
      return this.cache.get(technology);
    }

    const experts = await getDevPioneers({
      area: technology,
      count: 50,
      random: false
    });

    this.cache.set(technology, experts);
    return experts;
  }

  async recommendExperts(userInterests) {
    const recommendations = [];
    
    for (const interest of userInterests) {
      const experts = await this.getExpertsByTech(interest);
      recommendations.push(...experts.pioneers);
    }

    // 去重并按影响力排序
    const uniqueExperts = this.deduplicateExperts(recommendations);
    return this.rankByInfluence(uniqueExperts);
  }

  deduplicateExperts(experts) {
    const seen = new Set();
    return experts.filter(expert => {
      if (seen.has(expert.name)) return false;
      seen.add(expert.name);
      return true;
    });
  }

  rankByInfluence(experts) {
    return experts.sort((a, b) => {
      // 简单的影响力评分算法
      const scoreA = this.calculateInfluenceScore(a);
      const scoreB = this.calculateInfluenceScore(b);
      return scoreB - scoreA;
    });
  }

  calculateInfluenceScore(expert) {
    let score = 0;
    if (expert.has_github) score += 3;
    if (expert.has_twitter) score += 2;
    if (expert.has_linkedin) score += 1;
    if (expert.has_personal_page) score += 1;
    
    // 知名公司加分
    const topCompanies = ['Google', 'Meta', 'Microsoft', 'OpenAI'];
    if (topCompanies.includes(expert.Company)) score += 5;
    
    return score;
  }
}

// 使用示例
const recommender = new TechExpertRecommender();
const experts = await recommender.recommendExperts(['AI', 'Deep Learning', 'LLM']);
```

### 2. 构建技术趋势分析

```javascript
async function analyzeTechTrends() {
  const allPioneers = await getDevPioneers({ count: 50 });
  
  // 分析技术领域分布
  const areaCount = {};
  allPioneers.pioneers.forEach(pioneer => {
    const areas = pioneer.area.split(',').map(a => a.trim());
    areas.forEach(area => {
      areaCount[area] = (areaCount[area] || 0) + 1;
    });
  });

  // 分析公司分布
  const companyCount = {};
  allPioneers.pioneers.forEach(pioneer => {
    const company = pioneer.Company;
    if (company && company !== 'Unknown') {
      companyCount[company] = (companyCount[company] || 0) + 1;
    }
  });

  return {
    topAreas: Object.entries(areaCount)
      .sort(([,a], [,b]) => b - a)
      .slice(0, 10),
    topCompanies: Object.entries(companyCount)
      .sort(([,a], [,b]) => b - a)
      .slice(0, 10),
    totalPioneers: allPioneers.total_in_database
  };
}
```

---

## 🚨 注意事项

1. **数据更新**: 开发先驱数据来自静态CSV文件，更新频率较低
2. **图片链接**: 部分图片链接可能失效，建议实现图片加载失败的fallback
3. **链接有效性**: 外部链接（GitHub、Twitter等）的有效性不保证
4. **编码问题**: 部分非英文字符可能存在编码问题
5. **数据完整性**: 并非所有开发先驱都有完整的信息字段

---

## 🔗 相关文档

- [GitHub分析器流式API文档](./github_analyzer_streaming_api.md)
- [GitHub分析器API文档](./github_analyzer_api.md)
- [API使用指南](./api_usage_guide.md)

---

## 📞 支持与反馈

如果您在使用过程中遇到问题或有改进建议，请：

1. 检查本文档的常见问题部分
2. 查看服务器日志获取详细错误信息
3. 联系开发团队获取技术支持

**最后更新**: 2025年1月
