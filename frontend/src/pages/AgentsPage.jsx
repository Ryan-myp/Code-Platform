import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { Users, Plus, Edit2, Trash2, Bot, MessageSquare, Layers, Settings, Save, X, ChevronRight, Wrench, Search, FolderOpen, Send, Image as ImageIcon, Loader2 } from 'lucide-react'

const API = 'http://localhost:8888'

// Agno 完整内置工具列表（按类别分组）
const AGNO_TOOLS_CATEGORIES = [
  {
    name: '🔍 搜索与信息',
    tools: [
      { id: 'web_search', name: '网页搜索', desc: '通用网页搜索' },
      { id: 'duckduckgo', name: 'DuckDuckGo', desc: '隐私搜索引擎' },
      { id: 'tavily', name: 'Tavily Search', desc: 'AI 优化搜索' },
      { id: 'serper', name: 'Google Serper', desc: 'Google 搜索 API' },
      { id: 'bravesearch', name: 'Brave Search', desc: 'Brave 搜索引擎' },
      { id: 'searxng', name: 'SearXNG', desc: '元搜索引擎' },
      { id: 'searchapi', name: 'SearchAPI', desc: '多引擎搜索聚合' },
      { id: 'serpapi', name: 'SerpAPI', desc: 'SERP 数据提取' },
      { id: 'exa', name: 'Exa Search', desc: '语义搜索引擎' },
      { id: 'youcom', name: 'You.com', desc: 'AI 搜索' },
      { id: 'linkup', name: 'Linkup', desc: '链接发现' },
      { id: 'baidusearch', name: '百度搜索', desc: '中文搜索' },
      { id: 'brightdata', name: 'Bright Data', desc: '数据采集平台' },
      { id: 'oxylabs', name: 'Oxylabs', desc: '代理网络' },
      { id: 'scavio', name: 'Scavio', desc: '数据收集' },
      { id: 'seltz', name: 'Seltz', desc: '数据服务' },
      { id: 'jina', name: 'Jina Reader', desc: '内容读取' },
      { id: 'valyu', name: 'Valyu', desc: '数据索引' },
      { id: 'wikipedia', name: 'Wikipedia', desc: '维基百科搜索' },
      { id: 'arxiv', name: 'ArXiv', desc: '学术论文搜索' },
      { id: 'pubmed', name: 'PubMed', desc: '生物医学文献' },
      { id: 'hackernews', name: 'Hacker News', desc: 'HN 搜索' },
      { id: 'reddit', name: 'Reddit', desc: 'Reddit 搜索' },
      { id: 'openweather', name: 'OpenWeather', desc: '天气查询' },
      { id: 'google.maps', name: 'Google Maps', desc: '地图服务' },
    ]
  },
  {
    name: '💻 代码与开发',
    tools: [
      { id: 'python', name: 'Python 执行器', desc: '运行 Python 代码' },
      { id: 'coding', name: '代码生成', desc: 'AI 代码编写' },
      { id: 'shell', name: 'Shell 命令', desc: '执行 shell 命令' },
      { id: 'github', name: 'GitHub', desc: '仓库操作' },
      { id: 'gitlab', name: 'GitLab', desc: 'GitLab 操作' },
      { id: 'bitbucket', name: 'Bitbucket', desc: 'Atlassian Bitbucket' },
      { id: 'docker', name: 'Docker', desc: '容器管理' },
      { id: 'sql', name: 'SQL 查询', desc: '数据库查询' },
      { id: 'postgres', name: 'PostgreSQL', desc: 'Postgres 操作' },
      { id: 'duckdb', name: 'DuckDB', desc: '分析型数据库' },
      { id: 'neo4j', name: 'Neo4j', desc: '图数据库' },
      { id: 'redshift', name: 'Redshift', desc: 'AWS 数据仓库' },
      { id: 'google_bigquery', name: 'BigQuery', desc: 'Google 数据仓库' },
      { id: 'pandas', name: 'Pandas', desc: '数据分析' },
      { id: 'opencv', name: 'OpenCV', desc: '计算机视觉' },
      { id: 'e2b', name: 'E2B', desc: '云端沙箱' },
      { id: 'daytona', name: 'Daytona', desc: '开发环境' },
      { id: 'streamlit', name: 'Streamlit', desc: '快速构建 UI' },
      { id: 'visualization', name: '数据可视化', desc: '图表生成' },
      { id: 'file', name: '文件操作', desc: '读写文件' },
      { id: 'local_file_system', name: '本地文件系统', desc: '访问本地文件' },
      { id: 'file_generation', name: '文件生成', desc: '生成各种文件' },
      { id: 'csv_toolkit', name: 'CSV 工具', desc: 'CSV 处理' },
      { id: 'workspace', name: '工作空间', desc: '项目管理' },
      { id: 'airflow', name: 'Airflow', desc: '工作流编排' },
      { id: 'scheduler', name: '调度器', desc: '定时任务' },
      { id: 'workflow', name: '工作流', desc: '流程编排' },
      { id: 'apify', name: 'Apify', desc: '网络爬虫平台' },
      { id: 'browserbase', name: 'Browserbase', desc: '云端浏览器' },
      { id: 'spider', name: 'Spider', desc: '爬虫框架' },
      { id: 'sleep', name: '延迟', desc: '等待指定时间' },
    ]
  },
  {
    name: '🤖 AI 与模型',
    tools: [
      { id: 'models', name: '模型管理', desc: 'LLM 模型选择' },
      { id: 'reasoning', name: '推理引擎', desc: '复杂推理' },
      { id: 'models.gemini', name: 'Gemini', desc: 'Google Gemini' },
      { id: 'models.groq', name: 'Groq', desc: '高速推理' },
      { id: 'models.morph', name: 'Morph', desc: '模型路由' },
      { id: 'models.nebius', name: 'Nebius', desc: '云推理' },
      { id: 'models.azure_openai', name: 'Azure OpenAI', desc: 'Azure 服务' },
      { id: 'models_labs', name: '模型实验室', desc: '实验性模型' },
      { id: 'knowledge', name: '知识库', desc: '知识检索' },
      { id: 'mem0', name: 'Mem0', desc: '长期记忆' },
      { id: 'memory', name: '短期记忆', desc: '会话记忆' },
      { id: 'user_feedback', name: '用户反馈', desc: '反馈收集' },
      { id: 'user_control_flow', name: '控制流', desc: '流程控制' },
      { id: 'agentql', name: 'AgentQL', desc: '结构化查询' },
      { id: 'confluence', name: 'Confluence', desc: '文档协作' },
      { id: 'docling', name: 'Docling', desc: '文档解析' },
      { id: 'redmine', name: 'Redmine', desc: '项目管理' },
      { id: 'zendesk', name: 'Zendesk', desc: '客服系统' },
      { id: 'zep', name: 'Zep', desc: '对话记忆' },
      { id: 'webex', name: 'Webex', desc: 'Cisco 会议' },
    ]
  },
  {
    name: '📧 邮件与通讯',
    tools: [
      { id: 'email', name: '邮件', desc: '发送邮件' },
      { id: 'gmail', name: 'Gmail', desc: 'Gmail 管理' },
      { id: 'resend', name: 'Resend', desc: '事务邮件' },
      { id: 'aws_ses', name: 'AWS SES', desc: '亚马逊邮件服务' },
      { id: 'slack', name: 'Slack', desc: 'Slack 消息' },
      { id: 'discord', name: 'Discord', desc: 'Discord 消息' },
      { id: 'telegram', name: 'Telegram', desc: 'Telegram 消息' },
      { id: 'whatsapp', name: 'WhatsApp', desc: 'WhatsApp 消息' },
      { id: 'twilio', name: 'Twilio', desc: '通信服务' },
      { id: 'x', name: 'X (Twitter)', desc: '推特长文' },
      { id: 'antigravity', name: 'Antigravity', desc: '趣味工具' },
      { id: 'api', name: 'API 调用', desc: 'HTTP 请求' },
      { id: 'brandfetch', name: 'BrandFetch', desc: '品牌数据' },
      { id: 'desi_vocal', name: 'Desi Vocal', desc: '语音服务' },
      { id: 'lumalab', name: 'Luma Lab', desc: '视频生成' },
      { id: 'sofya', name: 'Sofya', desc: 'AI 服务' },
    ]
  },
  {
    name: '🏢 办公与协作',
    tools: [
      { id: 'notion', name: 'Notion', desc: 'Notion 集成' },
      { id: 'jira', name: 'Jira', desc: 'Atlassian Jira' },
      { id: 'linear', name: 'Linear', desc: '项目管理' },
      { id: 'trello', name: 'Trello', desc: '看板管理' },
      { id: 'todoist', name: 'Todoist', desc: '任务管理' },
      { id: 'clickup', name: 'ClickUp', desc: '任务管理' },
      { id: 'calcom', name: 'Cal.com', desc: '会议安排' },
      { id: 'google.calendar', name: 'Google 日历', desc: '日程管理' },
      { id: 'google.sheets', name: 'Google Sheets', desc: '电子表格' },
      { id: 'google.drive', name: 'Google Drive', desc: '云盘管理' },
      { id: 'google.slides', name: 'Google Slides', desc: '演示文稿' },
      { id: 'google.gmail', name: 'Gmail API', desc: '邮件 API' },
      { id: 'google.bigquery', name: 'BigQuery API', desc: '数据查询' },
      { id: 'google_drive', name: 'Google Drive API', desc: '云盘 API' },
      { id: 'google_maps', name: 'Maps API', desc: '地图 API' },
      { id: 'googlesheets', name: 'Sheets API', desc: '表格 API' },
      { id: 'googlecalendar', name: 'Calendar API', desc: '日历 API' },
      { id: 'newspaper', name: 'Newspaper', desc: '新闻文章提取' },
      { id: 'newspaper4k', name: 'Newspaper4K', desc: '高质量新闻提取' },
    ]
  },
  {
    name: '🎨 媒体与创意',
    tools: [
      { id: 'dalle', name: 'DALL-E', desc: '图像生成' },
      { id: 'fal', name: 'Fal', desc: 'AI 图像生成' },
      { id: 'replicate', name: 'Replicate', desc: '模型部署' },
      { id: 'unsplash', name: 'Unsplash', desc: '图片搜索' },
      { id: 'giphy', name: 'Giphy', desc: 'GIF 搜索' },
      { id: 'cartesia', name: 'Cartesia', desc: '语音合成' },
      { id: 'eleven_labs', name: 'ElevenLabs', desc: '语音合成' },
      { id: 'mlx_transcribe', name: 'MLX Transcribe', desc: '语音转文字' },
      { id: 'moviepy_video', name: 'MoviePy', desc: '视频编辑' },
      { id: 'twelvelabs', name: 'Twelve Labs', desc: '视频理解' },
      { id: 'nano_banana', name: 'Nano Banana', desc: '图像编辑' },
      { id: 'spotify', name: 'Spotify', desc: '音乐控制' },
      { id: 'youtube', name: 'YouTube', desc: '视频搜索' },
    ]
  },
  {
    name: '🛒 电商与商业',
    tools: [
      { id: 'salesforce', name: 'Salesforce', desc: 'CRM 管理' },
      { id: 'shopify', name: 'Shopify', desc: '电商管理' },
      { id: 'yfinance', name: 'Yahoo Finance', desc: '金融数据' },
      { id: 'financial_datasets', name: '金融数据集', desc: '市场数据' },
      { id: 'openbb', name: 'OpenBB', desc: '开放金融终端' },
      { id: 'aws_lambda', name: 'AWS Lambda', desc: '无服务器计算' },
      { id: 'evm', name: 'EVM', desc: '以太坊虚拟机' },
      { id: 'firecrawl', name: 'Firecrawl', desc: '网页抓取' },
      { id: 'crawl4ai', name: 'Crawl4AI', desc: 'AI 网页爬取' },
      { id: 'scrapegraph', name: 'ScrapeGraph', desc: '智能网页抓取' },
      { id: 'trafilatura', name: 'Trafilatura', desc: '文本提取' },
      { id: 'llms_txt', name: 'LLMs.txt', desc: 'LLM 文档发现' },
      { id: 'website', name: '网站浏览', desc: '浏览网页内容' },
    ]
  }
]

// 扁平化工具列表用于搜索
const ALL_TOOLS = AGNO_TOOLS_CATEGORIES.flatMap(cat => cat.tools)

export default function AgentsPage({ tab = 'agents' }) {
  const [agents, setAgents] = useState([])
  const [teams, setTeams] = useState([])
  const [workflows, setWorkflows] = useState([])
  const [activeTab, setActiveTab] = useState(tab)
  const [showForm, setShowForm] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const [formData, setFormData] = useState({})
  const [loading, setLoading] = useState(false)
  const [selectedTools, setSelectedTools] = useState([])
  const [toolSearch, setToolSearch] = useState('')
  const [expandedCategories, setExpandedCategories] = useState({})
  
  // 聊天相关状态
  const [chatOpen, setChatOpen] = useState(false)
  const [currentAgent, setCurrentAgent] = useState(null)
  const [messages, setMessages] = useState([])
  const [inputText, setInputText] = useState('')
  const [uploadedImage, setUploadedImage] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [conversations, setConversations] = useState([])
  const [selectedConversationId, setSelectedConversationId] = useState(null)
  const messagesEndRef = useRef(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    loadData()
  }, [activeTab])

  // 自动滚动到底部
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  const loadData = async () => {
    try {
      if (activeTab === 'agents') {
        const res = await axios.get(`${API}/api/agents`)
        setAgents(res.data)
      } else if (activeTab === 'teams') {
        const res = await axios.get(`${API}/api/teams`)
        setTeams(res.data)
      } else {
        const res = await axios.get(`${API}/api/workflows`)
        setWorkflows(res.data)
      }
    } catch (err) {
      console.error(err)
    }
  }

  const handleSubmit = async () => {
    setLoading(true)
    try {
      const submitData = { ...formData, tools: selectedTools }
      if (activeTab === 'agents') {
        if (editingItem) {
          await axios.put(`${API}/api/agents/${editingItem.id}`, submitData)
        } else {
          await axios.post(`${API}/api/agents`, submitData)
        }
      } else if (activeTab === 'teams') {
        await axios.post(`${API}/api/teams`, formData)
      } else {
        await axios.post(`${API}/api/workflows`, formData)
      }
      setShowForm(false)
      setEditingItem(null)
      setFormData({})
      setSelectedTools([])
      setToolSearch('')
      loadData()
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id) => {
    try {
      await axios.delete(`${API}/api/${activeTab}/${id}`)
      loadData()
    } catch (err) {
      console.error(err)
    }
  }

  // 打开聊天窗口 - 加载历史对话
  const openChat = async (agent) => {
    setCurrentAgent(agent)
    setMessages([])
    setSelectedConversationId(null)
    setUploadedImage(null)
    setInputText('')
    
    try {
      const res = await axios.get(`${API}/api/agents/${agent.id}/conversations`)
      setConversations(res.data)
    } catch (err) {
      console.error(err)
    }
    
    setChatOpen(true)
  }

  // 加载对话历史消息
  const loadConversation = async (convId) => {
    setSelectedConversationId(convId)
    try {
      const res = await axios.get(`${API}/api/conversations/${convId}`)
      setMessages(res.data.messages.map(m => ({
        role: m.role,
        content: m.content,
        timestamp: m.timestamp || new Date().toISOString()
      })))
    } catch (err) {
      console.error(err)
    }
  }

  // 创建新对话
  const createNewConversation = async () => {
    if (!currentAgent) return
    try {
      const res = await axios.post(`${API}/api/agents/${currentAgent.id}/conversations`)
      const convId = res.data.id
      setSelectedConversationId(convId)
      setMessages([{
        role: 'assistant',
        content: `你好！我是${currentAgent.name}，有什么可以帮你的吗？`,
        timestamp: new Date().toISOString()
      }])
      // 刷新对话列表
      const listRes = await axios.get(`${API}/api/agents/${currentAgent.id}/conversations`)
      setConversations(listRes.data)
    } catch (err) {
      console.error(err)
    }
  }

  // 删除对话
  const deleteConversation = async (convId, e) => {
    e.stopPropagation()
    try {
      await axios.delete(`${API}/api/conversations/${convId}`)
      if (selectedConversationId === convId) {
        setSelectedConversationId(null)
        setMessages([])
      }
      const res = await axios.get(`${API}/api/agents/${currentAgent.id}/conversations`)
      setConversations(res.data)
    } catch (err) {
      console.error(err)
    }
  }

  // 关闭聊天窗口
  const closeChat = () => {
    setChatOpen(false)
    setCurrentAgent(null)
  }

  // 上传图片
  const handleImageUpload = (e) => {
    const file = e.target.files[0]
    if (file) {
      const reader = new FileReader()
      reader.onloadend = () => {
        setUploadedImage(reader.result)
      }
      reader.readAsDataURL(file)
    }
  }

  // 发送消息
  const sendMessage = async () => {
    if (!inputText.trim() && !uploadedImage) return
    
    const userMessage = {
      role: 'user',
      content: inputText,
      image: uploadedImage,
      timestamp: new Date().toISOString()
    }
    
    setMessages(prev => [...prev, userMessage])
    setInputText('')
    setUploadedImage(null)
    setUploading(true)
    
    try {
      const payload = {
        task_type: 'chat',
        message: inputText,
        prd_text: inputText,
      }
      
      // Add conversation_id if exists
      if (selectedConversationId) {
        payload.conversation_id = selectedConversationId
      }
      
      const res = await axios.post(`${API}/api/agents/${currentAgent.id}/run`, payload)
      
      const assistantMessage = {
        role: 'assistant',
        content: res.data.result || '抱歉，我没有收到回复。',
        timestamp: new Date().toISOString()
      }
      
      setMessages(prev => [...prev, assistantMessage])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `错误：${err.response?.data?.result || err.message}`,
        timestamp: new Date().toISOString()
      }])
    } finally {
      setUploading(false)
    }
  }

  // 按回车发送
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const toggleTool = (toolId) => {
    setSelectedTools(prev =>
      prev.includes(toolId)
        ? prev.filter(t => t !== toolId)
        : [...prev, toolId]
    )
  }

  const toggleCategory = (index) => {
    setExpandedCategories(prev => ({
      ...prev,
      [index]: !prev[index]
    }))
  }

  const tabs = [
    { key: 'agents', label: 'Agent 管理', icon: Bot },
    { key: 'teams', label: 'Team 管理', icon: Users },
    { key: 'workflows', label: 'Workflow 管理', icon: Layers },
  ]

  // 根据搜索过滤工具
  const getFilteredTools = () => {
    if (!toolSearch.trim()) {
      return AGNO_TOOLS_CATEGORIES.map((cat, idx) => ({ ...cat, index: idx, tools: cat.tools }))
    }
    const filtered = ALL_TOOLS.filter(t =>
      t.name.toLowerCase().includes(toolSearch.toLowerCase()) ||
      t.desc.toLowerCase().includes(toolSearch.toLowerCase()) ||
      t.id.toLowerCase().includes(toolSearch.toLowerCase())
    )
    return [{ name: '搜索结果', tools: filtered, isSearch: true }]
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-purple-600 to-indigo-700 rounded-2xl shadow-lg mb-6">
            <Bot className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-4xl font-extrabold text-gray-900 tracking-tight mb-3">AI 智能体管理平台</h1>
          <p className="text-lg text-gray-500 max-w-2xl mx-auto">可视化创建和管理 Agent、Team 和 Workflow — 支持 {ALL_TOOLS.length} 个内置工具</p>
        </div>

        {/* Tabs */}
        <div className="flex space-x-2 mb-8 justify-center">
          {tabs.map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center px-6 py-3 rounded-xl font-medium transition-all duration-200 ${
                activeTab === tab.key
                  ? 'bg-purple-600 text-white shadow-lg'
                  : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200'
              }`}
            >
              <tab.icon className="w-5 h-5 mr-2" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Action Bar */}
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold text-gray-900">
            {activeTab === 'agents' ? 'Agent 列表' : activeTab === 'teams' ? 'Team 列表' : 'Workflow 列表'}
          </h2>
          <button
            onClick={() => { setShowForm(true); setEditingItem(null); setFormData({}); setSelectedTools([]); setToolSearch(''); }}
            className="flex items-center px-6 py-3 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-xl hover:from-purple-700 hover:to-indigo-700 font-bold transition-all shadow-lg hover:shadow-xl"
          >
            <Plus className="w-5 h-5 mr-2" />
            新建{activeTab === 'agents' ? 'Agent' : activeTab === 'teams' ? 'Team' : 'Workflow'}
          </button>
        </div>

        {/* Form Modal */}
        {showForm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto">
              <div className="p-6 border-b border-gray-100 flex justify-between items-center sticky top-0 bg-white z-10">
                <h3 className="text-xl font-bold">{editingItem ? '编辑' : '新建'}{activeTab === 'agents' ? 'Agent' : activeTab === 'teams' ? 'Team' : 'Workflow'}</h3>
                <button onClick={() => setShowForm(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="p-6 space-y-4">
                {activeTab === 'agents' && (
                  <>
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">名称 *</label>
                      <input type="text" className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10"
                        value={formData.name || ''} onChange={e => setFormData({...formData, name: e.target.value})} placeholder="例如：产品经理" />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">角色描述 / Prompt</label>
                      <textarea className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10 h-32 resize-none"
                        value={formData.instructions || ''} onChange={e => setFormData({...formData, instructions: e.target.value})}
                        placeholder="例如：你是一个资深产品经理，擅长写PRD..." />
                    </div>
                    
                    {/* 工具选择 - 分类展示 */}
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2 flex items-center justify-between">
                        <span className="flex items-center"><Wrench className="w-4 h-4 mr-2" />内置工具（{ALL_TOOLS.length} 个可用，已选 {selectedTools.length} 个）</span>
                      </label>
                      
                      {/* 搜索框 */}
                      <div className="relative mb-4">
                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                        <input
                          type="text"
                          className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10 text-sm"
                          placeholder="🔍 搜索工具名称或描述..."
                          value={toolSearch}
                          onChange={e => setToolSearch(e.target.value)}
                        />
                      </div>
                      
                      {/* 工具网格 - 分类或搜索模式 */}
                      <div className="space-y-3 max-h-80 overflow-y-auto pr-2">
                        {getFilteredTools().map((group, groupIdx) => (
                          <div key={groupIdx}>
                            {!group.isSearch && (
                              <button 
                                onClick={() => toggleCategory(group.index)}
                                className="flex items-center space-x-2 text-sm font-bold text-gray-700 mb-2 hover:text-purple-600 transition-colors"
                              >
                                <FolderOpen className={`w-4 h-4 transition-transform ${expandedCategories[group.index] ? 'rotate-90' : ''}`} />
                                <span>{group.name}</span>
                                <span className="text-xs font-normal text-gray-400">({group.tools.length})</span>
                              </button>
                            )}
                            {(!group.isSearch && !expandedCategories[group.index]) ? null : (
                              <div className={`grid gap-2 ${group.isSearch ? 'grid-cols-2 md:grid-cols-3 lg:grid-cols-4' : 'grid-cols-2 md:grid-cols-3 lg:grid-cols-4'}`}>
                                {group.tools.map(tool => (
                                  <label
                                    key={tool.id}
                                    className={`flex items-start space-x-2 p-2 rounded-lg cursor-pointer transition-all text-xs ${
                                      selectedTools.includes(tool.id)
                                        ? 'bg-purple-100 border-2 border-purple-400 shadow-sm'
                                        : 'hover:bg-gray-50 border border-gray-200'
                                    }`}
                                  >
                                    <input
                                      type="checkbox"
                                      checked={selectedTools.includes(tool.id)}
                                      onChange={() => toggleTool(tool.id)}
                                      className="w-3.5 h-3.5 mt-0.5 text-purple-600 rounded focus:ring-purple-500 flex-shrink-0"
                                    />
                                    <div className="min-w-0">
                                      <span className="font-medium text-gray-900 block truncate">{tool.name}</span>
                                      <span className="text-gray-500 block truncate">{tool.desc}</span>
                                    </div>
                                  </label>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                      {getFilteredTools()[0]?.tools.length === 0 && (
                        <p className="text-center text-gray-400 py-4">没有找到匹配的工具</p>
                      )}
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <label className="flex items-center space-x-2 p-3 border border-gray-200 rounded-xl cursor-pointer hover:bg-gray-50">
                        <input type="checkbox" checked={formData.enable_memory || false} onChange={e => setFormData({...formData, enable_memory: e.target.checked})}
                          className="w-4 h-4 text-purple-600 rounded focus:ring-purple-500" />
                        <span className="text-sm font-medium">启用记忆</span>
                      </label>
                      <label className="flex items-center space-x-2 p-3 border border-gray-200 rounded-xl cursor-pointer hover:bg-gray-50">
                        <input type="checkbox" checked={formData.enable_reasoning || false} onChange={e => setFormData({...formData, enable_reasoning: e.target.checked})}
                          className="w-4 h-4 text-purple-600 rounded focus:ring-purple-500" />
                        <span className="text-sm font-medium">启用思考</span>
                      </label>
                    </div>
                  </>
                )}
                {activeTab === 'teams' && (
                  <>
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">团队名称 *</label>
                      <input type="text" className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10"
                        value={formData.name || ''} onChange={e => setFormData({...formData, name: e.target.value})} placeholder="例如：方案设计团队" />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">协作模式</label>
                      <select className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10"
                        value={formData.mode || 'coordinate'} onChange={e => setFormData({...formData, mode: e.target.value})}>
                        <option value="coordinate">协调模式 - 统一分配任务</option>
                        <option value="route">路由模式 - 自动选择执行者</option>
                        <option value="delegate">委派模式 - 逐级委派</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">成员 Agent ID（逗号分隔）</label>
                      <input type="text" className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10"
                        value={formData.members?.join(', ') || ''}
                        onChange={e => setFormData({...formData, members: e.target.value.split(',').map(s => s.trim())})}
                        placeholder="agent_xxx, agent_yyy" />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">团队指令</label>
                      <textarea className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10 h-24 resize-none"
                        value={formData.instructions || ''} onChange={e => setFormData({...formData, instructions: e.target.value})}
                        placeholder="团队的工作目标和规则..." />
                    </div>
                  </>
                )}
                {activeTab === 'workflows' && (
                  <>
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">工作流名称 *</label>
                      <input type="text" className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10"
                        value={formData.name || ''} onChange={e => setFormData({...formData, name: e.target.value})} placeholder="例如：完整研发流程" />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">步骤配置（JSON）</label>
                      <textarea className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10 h-48 font-mono text-sm"
                        value={JSON.stringify(formData.steps || [{agent_id: '', name: '第一步'}], null, 2)}
                        onChange={e => {try {setFormData({...formData, steps: JSON.parse(e.target.value)})} catch {} }}
                        placeholder='[{"agent_id": "agent_xxx", "name": "PRD编写"}, {"agent_id": "agent_yyy", "name": "代码生成"}]' />
                    </div>
                  </>
                )}
              </div>
              <div className="p-6 border-t border-gray-100 flex space-x-3 sticky bottom-0 bg-white">
                <button onClick={() => setShowForm(false)} className="flex-1 px-6 py-3 border border-gray-300 rounded-xl hover:bg-gray-50 font-medium">取消</button>
                <button onClick={handleSubmit} disabled={loading} className="flex-1 px-6 py-3 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-xl hover:from-purple-700 hover:to-indigo-700 disabled:opacity-50 font-bold flex items-center justify-center">
                  {loading ? <><div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div>保存中...</> : <><Save className="w-5 h-5 mr-2" />保存</>}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* List */}
        <div className="space-y-4">
          {(activeTab === 'agents' ? agents : activeTab === 'teams' ? teams : workflows).length === 0 ? (
            <div className="text-center py-16 bg-white rounded-2xl border border-gray-100">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                {activeTab === 'agents' ? <Bot className="w-8 h-8 text-gray-400" /> : activeTab === 'teams' ? <Users className="w-8 h-8 text-gray-400" /> : <Layers className="w-8 h-8 text-gray-400" />}
              </div>
              <p className="text-gray-500 text-lg">暂无数据，点击"新建"开始创建</p>
            </div>
          ) : (
            (activeTab === 'agents' ? agents : activeTab === 'teams' ? teams : workflows).map(item => (
              <div key={item.id} className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 hover:shadow-xl transition-shadow">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-2">
                      <span className="px-3 py-1 bg-purple-100 text-purple-700 rounded-lg text-sm font-bold">{item.id.split('_')[0].toUpperCase()}</span>
                      <h3 className="text-xl font-bold text-gray-900">{item.name}</h3>
                    </div>
                    {item.description && <p className="text-gray-600 mb-2">{item.description}</p>}
                    {item.instructions && <p className="text-sm text-gray-500 mb-3 line-clamp-2">{item.instructions}</p>}
                    {activeTab === 'agents' && (
                      <div className="flex flex-wrap gap-2">
                        {item.enable_memory && <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded-md text-xs font-medium">记忆</span>}
                        {item.enable_reasoning && <span className="px-2 py-1 bg-green-100 text-green-700 rounded-md text-xs font-medium">思考</span>}
                        {item.tools && item.tools.length > 0 && (
                          <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded-md text-xs font-medium">
                            {item.tools.length} 个工具
                          </span>
                        )}
                      </div>
                    )}
                    {activeTab === 'teams' && item.members && (
                      <div className="mt-2">
                        <span className="text-sm text-gray-500">成员: {item.members.join(', ')}</span>
                        <span className="ml-2 px-2 py-1 bg-indigo-100 text-indigo-700 rounded-md text-xs font-medium capitalize">{item.mode}</span>
                      </div>
                    )}
                  </div>
                  <div className="flex space-x-2">
                    <button onClick={() => { setEditingItem(item); setFormData(item); setSelectedTools(item.tools || []); setShowForm(true); }}
                      className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
                      <Edit2 className="w-4 h-4 text-gray-600" />
                    </button>
                    <button onClick={() => handleDelete(item.id)}
                      className="p-2 hover:bg-red-50 rounded-lg transition-colors">
                      <Trash2 className="w-4 h-4 text-red-600" />
                    </button>
                    {activeTab === 'agents' && (
                      <button onClick={() => openChat(item)}
                        className="px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg hover:from-purple-700 hover:to-indigo-700 font-medium text-sm flex items-center">
                        <MessageSquare className="w-4 h-4 mr-1" />
                        对话
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Chat Modal */}
      {chatOpen && currentAgent && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl h-[80vh] flex flex-col">
            {/* Header */}
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-gradient-to-br from-purple-600 to-indigo-600 rounded-full flex items-center justify-center">
                  <Bot className="w-6 h-6 text-white" />
                </div>
                <div className="flex-1">
                  <h3 className="font-bold text-gray-900">{currentAgent.name}</h3>
                  <p className="text-xs text-gray-500">{currentAgent.instructions || '未设置角色描述'}</p>
                </div>
              </div>
              <div className="flex items-center space-x-2 mr-2">
                <button onClick={createNewConversation} className="px-3 py-1.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm font-medium flex items-center">
                  <Plus className="w-4 h-4 mr-1" /> 新对话
                </button>
                <button onClick={closeChat} className="p-2 hover:bg-gray-100 rounded-lg">
                  <X className="w-5 h-5 text-gray-500" />
                </button>
              </div>
            </div>

            {/* Conversation List */}
            <div className="px-4 py-2 bg-gray-50 border-b border-gray-200">
              <div className="flex items-center space-x-2 overflow-x-auto scrollbar-hide">
                <span className="text-xs font-medium text-gray-500 whitespace-nowrap">历史对话：</span>
                {conversations.length === 0 ? (
                  <span className="text-xs text-gray-400">暂无对话，点击"新对话"开始</span>
                ) : (
                  conversations.map(conv => (
                    <div key={conv.id} className="relative group flex-shrink-0">
                      <button
                        onClick={() => loadConversation(conv.id)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                          selectedConversationId === conv.id
                            ? 'bg-purple-600 text-white'
                            : 'bg-white text-gray-700 border border-gray-200 hover:border-purple-300'
                        }`}
                      >
                        {conv.title || '未命名对话'}
                        <span className="ml-1 opacity-70">({conv.message_count || 0})</span>
                      </button>
                      <button
                        onClick={(e) => deleteConversation(conv.id, e)}
                        className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white rounded-full flex items-center justify-center text-[10px] opacity-0 group-hover:opacity-100 hover:bg-red-600 transition-opacity"
                        title="删除对话"
                      >
                        ×
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[80%] rounded-2xl p-4 ${
                    msg.role === 'user' 
                      ? 'bg-purple-600 text-white' 
                      : 'bg-gray-100 text-gray-900'
                  }`}>
                    {msg.image && (
                      <img src={msg.image} alt="Uploaded" className="max-w-full rounded-lg mb-2" />
                    )}
                    <div className="prose prose-sm max-w-none">
                      {msg.content}
                    </div>
                    <div className={`text-xs mt-2 ${msg.role === 'user' ? 'text-purple-200' : 'text-gray-500'}`}>
                      {new Date(msg.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              ))}
              {uploading && (
                <div className="flex justify-start">
                  <div className="bg-gray-100 rounded-2xl p-4">
                    <Loader2 className="w-5 h-5 animate-spin text-purple-600" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-4 border-t border-gray-200">
              {/* Image Preview */}
              {uploadedImage && (
                <div className="mb-3 relative inline-block">
                  <img src={uploadedImage} alt="Preview" className="h-20 rounded-lg border border-gray-200" />
                  <button 
                    onClick={() => setUploadedImage(null)}
                    className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center text-xs hover:bg-red-600"
                  >
                    ×
                  </button>
                </div>
              )}
              
              <div className="flex items-end space-x-2">
                {/* Image Upload Button */}
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="p-2 text-gray-500 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                  title="上传图片"
                >
                  <ImageIcon className="w-5 h-5" />
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleImageUpload}
                  className="hidden"
                />
                
                {/* Text Input */}
                <textarea
                  className="flex-1 p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10 resize-none text-sm"
                  placeholder="输入消息... (Enter 发送，Shift+Enter 换行)"
                  value={inputText}
                  onChange={e => setInputText(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={2}
                />
                
                {/* Send Button */}
                <button
                  onClick={sendMessage}
                  disabled={!inputText.trim() && !uploadedImage || uploading}
                  className="p-3 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-xl hover:from-purple-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                >
                  <Send className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
