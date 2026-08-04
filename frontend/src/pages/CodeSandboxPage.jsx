import React, { useState, useRef } from 'react'
import { Play, Terminal, Trash2, Clock, Download, Copy, Code, Loader2, Zap } from 'lucide-react'
import { Card, Button, Empty, PageHeader } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const TEMPLATES = [
  { label: '数据分析', code: `import pandas as pd
import numpy as np

# 生成示例数据
data = pd.DataFrame({
    '月份': ['1月','2月','3月','4月','5月','6月'],
    '销售额': [120, 135, 148, 162, 175, 190],
    '成本': [80, 88, 95, 100, 108, 115]
})

# 计算利润和利润率
data['利润'] = data['销售额'] - data['成本']
data['利润率'] = (data['利润'] / data['销售额'] * 100).round(1)

print("=== 销售数据分析 ===")
print(data.to_string(index=False))
print(f"\\n总销售额: {data['销售额'].sum()} 万元")
print(f"总利润: {data['利润'].sum()} 万元")
print(f"平均利润率: {data['利润率'].mean()}%")` },
  { label: '算法演示', code: `# 快速排序算法
def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)

# 测试
test_data = [64, 34, 25, 12, 22, 11, 90, 5, 77, 42]
print(f"原始数组: {test_data}")
print(f"排序结果: {quicksort(test_data)}")
print(f"时间复杂度: O(n log n)")` },
  { label: '可视化', code: `import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io, base64

# 创建图表
fig, ax = plt.subplots(figsize=(8, 4))
x = [1, 2, 3, 4, 5, 6]
y1 = [120, 135, 148, 162, 175, 190]
y2 = [80, 88, 95, 100, 108, 115]

ax.plot(x, y1, 'b-o', label='销售额')
ax.plot(x, y2, 'r-s', label='成本')
ax.fill_between(x, y2, y1, alpha=0.2, color='green', label='利润')
ax.set_xlabel('月份')
ax.set_ylabel('金额（万元）')
ax.set_title('销售趋势图')
ax.legend()
ax.grid(True, alpha=0.3)

buf = io.BytesIO()
plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
buf.seek(0)
img_base64 = base64.b64encode(buf.read()).decode()
print(f"[IMAGE]{img_base64}[/IMAGE]")
plt.close()` },
]

export default function CodeSandboxPage() {
  const toast = useToast()
  const [code, setCode] = useState(TEMPLATES[0].code)
  const [output, setOutput] = useState('')
  const [running, setRunning] = useState(false)
  const [history, setHistory] = useState([])
  const outputRef = useRef(null)

  const runCode = async () => {
    if (!code.trim()) return
    setRunning(true); setOutput('')
    try {
      const res = await api.post('/api/sandbox/execute', { code: code.trim(), language: 'python' })
      const result = res.data.output || res.data.error || '(无输出)'
      setOutput(result)
      setHistory((prev) => [{ code: code.trim(), output: result, time: new Date().toISOString() }, ...prev.slice(0, 19)])
    } catch (e) {
      setOutput(`执行失败：${e.message}`)
    }
    setRunning(false)
  }

  const clearOutput = () => setOutput('')

  const renderOutput = (text) => {
    if (!text) return null
    // 处理内嵌图片
    const imgMatch = text.match(/\[IMAGE\]([\s\S]*?)\[\/IMAGE\]/)
    if (imgMatch) {
      const before = text.slice(0, text.indexOf('[IMAGE]'))
      const after = text.slice(text.indexOf('[/IMAGE]') + 9)
      return (
        <div>
          {before && <pre className="text-green-400 whitespace-pre-wrap font-mono text-xs">{before}</pre>}
          <img src={`data:image/png;base64,${imgMatch[1]}`} alt="chart" className="max-w-full rounded-lg my-2" />
          {after && <pre className="text-green-400 whitespace-pre-wrap font-mono text-xs">{after}</pre>}
        </div>
      )
    }
    return <pre className="text-green-400 whitespace-pre-wrap font-mono text-xs">{text}</pre>
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI代码解释器"
        description="在线编写并运行Python代码：数据分析、算法演示、可视化图表，即写即得"
        icon={Terminal}
        iconColor="from-gray-700 to-gray-900"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：模板 + 历史 */}
        <div className="space-y-4">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-500" /> 快速模板
            </h3>
            <div className="space-y-2">
              {TEMPLATES.map((t, i) => (
                <button key={i} onClick={() => setCode(t.code)}
                  className="w-full text-left px-3 py-2 rounded-lg bg-gray-50 hover:bg-amber-50 text-sm text-gray-700 hover:text-amber-700 transition-colors">
                  <Code className="w-3 h-3 inline mr-1.5 text-gray-400" />
                  {t.label}
                </button>
              ))}
            </div>
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-gray-500" /> 运行历史（{history.length}）
            </h3>
            {history.length === 0 ? (
              <div className="text-xs text-gray-400 text-center py-4">暂无记录</div>
            ) : (
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {history.map((h, i) => (
                  <button key={i} onClick={() => { setCode(h.code); setOutput(h.output) }}
                    className="w-full text-left p-2 rounded-lg hover:bg-gray-50 text-xs">
                    <div className="font-medium text-gray-700 truncate font-mono">{h.code.slice(0, 60)}...</div>
                    <div className="text-gray-400">{new Date(h.time).toLocaleTimeString()}</div>
                  </button>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* 右侧：编辑器 + 输出 */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Code className="w-4 h-4 text-gray-700" /> Python 代码
              </h3>
              <div className="flex items-center gap-2">
                <Button variant="secondary" size="sm" icon={Copy}
                  onClick={() => { navigator.clipboard.writeText(code); toast.success('已复制') }}>
                  复制
                </Button>
                <Button variant="primary" size="sm" icon={running ? Loader2 : Play}
                  loading={running} onClick={runCode}>
                  {running ? '运行中' : '运行'}
                </Button>
              </div>
            </div>
            <textarea
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="输入Python代码..."
              rows={14}
              spellCheck={false}
              className="w-full px-4 py-3 bg-gray-900 text-green-400 font-mono text-sm rounded-xl border-0 focus:ring-2 focus:ring-gray-500 outline-none resize-y"
            />
          </Card>

          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Terminal className="w-4 h-4 text-gray-700" /> 输出
              </h3>
              {output && (
                <Button variant="ghost" size="sm" icon={Trash2} onClick={clearOutput}>清空</Button>
              )}
            </div>
            {!output ? (
              <Empty icon={Terminal} title="等待运行" description="编写代码后点击「运行」查看结果" />
            ) : (
              <div ref={outputRef} className="p-4 bg-gray-900 rounded-xl min-h-[100px] max-h-[400px] overflow-y-auto">
                {renderOutput(output)}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
