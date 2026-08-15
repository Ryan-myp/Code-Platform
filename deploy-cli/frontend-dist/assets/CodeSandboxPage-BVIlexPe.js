import{j as e}from"./markdown-g0s9yNkx.js";import{r as i,ai as b,Z as F,_ as C,c7 as M,F as $,T as S,aA as k,at as H,L as q,A as K,bJ as J}from"./icons-CuryWb6C.js";import{u as X,a as I,B as d}from"./index-BvC8Lxt4.js";import{C as h}from"./Card-D-40z7ib.js";import{E as Y}from"./Empty-CNAzzaHY.js";import{P as Z}from"./PageHeader-vxHoe-m8.js";import{S as V}from"./ShareButton-BkoEjXkq.js";import{u as Q}from"./usePersistentToolState-B-HK4S-_.js";import"./tiptap-CnL2WxJ7.js";import"./mermaid-_EORGGBD.js";import"./lodash-C2t60yxh.js";import"./dateutils-Bc0X15j9.js";import"./http-DhXgJQ-f.js";const E="codesandbox_history_v1",L=20,W={allowed_imports:["math","numpy","pandas","matplotlib","PIL","random","json","statistics","collections","itertools","re"],limits:{code_max_len:2e4,output_max_len:307200,timeout_sec:30,cpu_sec:10,file_max_bytes:2097152}},ee=["numpy","pandas","matplotlib","PIL","math","statistics"],te=["os","subprocess","socket","open(","eval(","exec(","importlib","requests","shutil"],T=[{label:"数据分析",code:`import pandas as pd
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
print(f"平均利润率: {data['利润率'].mean()}%")`},{label:"算法演示",code:`# 快速排序算法
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
print(f"时间复杂度: O(n log n)")`},{label:"可视化",code:`import matplotlib
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
plt.close()`}];function he(){var v,N,w,_;const x=X(),[O,A]=Q("code_sandbox_editor",{code:T[0].code},{version:1,maxBytes:200*1024}),r=O.code,g=t=>A(s=>({...s,code:typeof t=="function"?t(s.code):t})),[l,m]=i.useState(""),[f,y]=i.useState(!1),[c,j]=i.useState(()=>{try{const t=localStorage.getItem(E);return t?JSON.parse(t):[]}catch{return[]}}),R=i.useRef(null),[p,P]=i.useState(W);i.useEffect(()=>{I.get("/api/sandbox/info").then(t=>t.data&&P(t.data)).catch(()=>{})},[]),i.useEffect(()=>{try{localStorage.setItem(E,JSON.stringify(c.slice(0,L)))}catch{}},[c]);const B=async()=>{if(r.trim()){y(!0),m("");try{const t=await I.post("/api/sandbox/execute",{code:r.trim(),language:"python"}),s=t.data.output||t.data.error||"(无输出)";m(s),j(o=>[{code:r.trim(),output:s,time:new Date().toISOString()},...o.slice(0,L-1)])}catch(t){m(`执行失败：${t.message}`)}y(!1)}},D=()=>m(""),U=()=>{if(!r.trim())return;const t=new Blob([r],{type:"text/x-python;charset=utf-8"}),s=URL.createObjectURL(t),o=document.createElement("a");o.href=s,o.download=`sandbox_${Date.now()}.py`,o.click(),URL.revokeObjectURL(s),x.success("代码已下载为 .py 文件")},z=()=>{if(!l){x.error("没有可导出的运行结果");return}const t=u=>u.replace(/\[IMAGE\][\s\S]*?\[\/IMAGE\]/g,`
[图表已内嵌，请查看页面渲染]
`),s=`# Python 运行结果

运行时间：${new Date().toLocaleString("zh-CN")}

## 代码

\`\`\`python
${r.trim()}
\`\`\`

## 输出

\`\`\`text
${t(l)}
\`\`\`
`,o=new Blob([s],{type:"text/markdown;charset=utf-8"}),n=URL.createObjectURL(o),a=document.createElement("a");a.href=n,a.download=`sandbox-result-${Date.now()}.md`,document.body.appendChild(a),a.click(),a.remove(),setTimeout(()=>URL.revokeObjectURL(n),3e3),x.success("运行结果已导出")},G=t=>{if(!t)return null;const s=[],o=/\[IMAGE\]([\s\S]*?)\[\/IMAGE\]/g;let n=0,a,u=0;for(;(a=o.exec(t))!==null;)a.index>n&&s.push(e.jsx("pre",{className:"text-green-400 whitespace-pre-wrap font-mono text-xs",children:t.slice(n,a.index)},u++)),s.push(e.jsx("img",{src:`data:image/png;base64,${a[1]}`,alt:"chart",className:"max-w-full rounded-lg my-2"},u++)),n=a.index+a[0].length;return n<t.length&&s.push(e.jsx("pre",{className:"text-green-400 whitespace-pre-wrap font-mono text-xs",children:t.slice(n)},u++)),s.length===0?e.jsx("pre",{className:"text-green-400 whitespace-pre-wrap font-mono text-xs",children:t}):e.jsx("div",{children:s})};return e.jsxs("div",{className:"space-y-6",children:[e.jsx(Z,{title:"AI代码解释器",description:"在线编写并运行Python代码：数据分析、算法演示、可视化图表，即写即得",icon:b,iconColor:"from-gray-700 to-gray-900"}),e.jsxs("div",{className:"grid grid-cols-1 lg:grid-cols-3 gap-6",children:[e.jsxs("div",{className:"space-y-4",children:[e.jsxs(h,{children:[e.jsxs("h3",{className:"font-semibold text-gray-900 mb-3 flex items-center gap-2",children:[e.jsx(F,{className:"w-4 h-4 text-amber-500"})," 快速模板"]}),e.jsx("div",{className:"space-y-2",children:T.map((t,s)=>e.jsxs("button",{onClick:()=>g(t.code),className:"w-full text-left px-3 py-2 rounded-lg bg-gray-50 hover:bg-amber-50 text-sm text-gray-700 hover:text-amber-700 transition-colors",children:[e.jsx(C,{className:"w-3 h-3 inline mr-1.5 text-gray-400"}),t.label]},s))})]}),e.jsxs(h,{children:[e.jsxs("h3",{className:"font-semibold text-gray-900 mb-3 flex items-center gap-2",children:[e.jsx(M,{className:"w-4 h-4 text-emerald-500"})," 沙箱环境说明"]}),e.jsxs("div",{className:"space-y-3",children:[e.jsxs("div",{children:[e.jsx("div",{className:"text-xs text-gray-500 mb-1.5",children:"可用库（白名单）"}),e.jsx("div",{className:"flex flex-wrap gap-1",children:(p.allowed_imports||[]).map(t=>e.jsx("span",{className:`px-1.5 py-0.5 rounded text-[10px] font-mono border ${ee.includes(t)?"bg-emerald-50 border-emerald-200 text-emerald-700":"bg-gray-50 border-gray-200 text-gray-500"}`,children:t},t))})]}),e.jsxs("div",{children:[e.jsx("div",{className:"text-xs text-gray-500 mb-1.5",children:"禁止操作（静态扫描拦截）"}),e.jsx("div",{className:"flex flex-wrap gap-1",children:te.map(t=>e.jsx("span",{className:"px-1.5 py-0.5 rounded text-[10px] font-mono bg-red-50 border border-red-100 text-red-500",children:t},t))})]}),e.jsxs("div",{className:"pt-2 border-t border-gray-100 grid grid-cols-2 gap-1.5 text-[11px] text-gray-500",children:[e.jsxs("div",{children:["⏱ 超时：",((v=p.limits)==null?void 0:v.timeout_sec)||30,"s"]}),e.jsxs("div",{children:["⚙️ CPU：",((N=p.limits)==null?void 0:N.cpu_sec)||10,"s"]}),e.jsxs("div",{children:["📄 代码上限：",((((w=p.limits)==null?void 0:w.code_max_len)||2e4)/1024).toFixed(0),"KB"]}),e.jsxs("div",{children:["📊 输出上限：",((((_=p.limits)==null?void 0:_.output_max_len)||307200)/1024).toFixed(0),"KB"]})]})]})]}),e.jsxs(h,{children:[e.jsxs("div",{className:"flex items-center justify-between mb-3",children:[e.jsxs("h3",{className:"font-semibold text-gray-900 flex items-center gap-2",children:[e.jsx($,{className:"w-4 h-4 text-gray-500"})," 运行历史（",c.length,"）"]}),c.length>0&&e.jsxs("button",{onClick:()=>j([]),className:"flex items-center gap-1 px-2 py-1 text-[11px] text-gray-400 hover:text-red-500 rounded-md transition-colors",children:[e.jsx(S,{className:"w-3 h-3"})," 清空"]})]}),c.length===0?e.jsx("div",{className:"text-xs text-gray-400 text-center py-4",children:"暂无记录"}):e.jsx("div",{className:"space-y-1 max-h-64 overflow-y-auto",children:c.map((t,s)=>e.jsxs("button",{onClick:()=>{g(t.code),m(t.output)},className:"w-full text-left p-2 rounded-lg hover:bg-gray-50 text-xs",children:[e.jsxs("div",{className:"font-medium text-gray-700 truncate font-mono",children:[t.code.slice(0,60),"..."]}),e.jsx("div",{className:"text-gray-400",children:new Date(t.time).toLocaleTimeString()})]},s))})]})]}),e.jsxs("div",{className:"lg:col-span-2 space-y-4",children:[e.jsxs(h,{children:[e.jsxs("div",{className:"flex items-center justify-between mb-3",children:[e.jsxs("h3",{className:"font-semibold text-gray-900 flex items-center gap-2",children:[e.jsx(C,{className:"w-4 h-4 text-gray-700"})," Python 代码"]}),e.jsxs("div",{className:"flex items-center gap-2",children:[e.jsx(d,{variant:"secondary",size:"sm",icon:k,onClick:()=>{navigator.clipboard.writeText(r),x.success("已复制")},children:"复制"}),e.jsx(d,{variant:"secondary",size:"sm",icon:H,onClick:U,children:"下载"}),e.jsx(V,{content:r,title:"Python 代码分享",contentType:"code"}),e.jsx(d,{variant:"primary",size:"sm",icon:f?q:K,loading:f,onClick:B,children:f?"运行中":"运行"})]})]}),e.jsx("textarea",{value:r,onChange:t=>g(t.target.value),placeholder:"输入Python代码...",rows:14,spellCheck:!1,className:"w-full px-4 py-3 bg-gray-900 text-green-400 font-mono text-sm rounded-xl border-0 focus:ring-2 focus:ring-gray-500 outline-none resize-y"})]}),e.jsxs(h,{children:[e.jsxs("div",{className:"flex items-center justify-between mb-3",children:[e.jsxs("h3",{className:"font-semibold text-gray-900 flex items-center gap-2",children:[e.jsx(b,{className:"w-4 h-4 text-gray-700"})," 输出"]}),l&&e.jsxs("div",{className:"flex items-center gap-2",children:[e.jsx(d,{variant:"ghost",size:"sm",icon:J,onClick:z,title:"导出代码与运行结果",children:"导出结果"}),e.jsx(d,{variant:"ghost",size:"sm",icon:k,onClick:()=>{navigator.clipboard.writeText(l),x.success("输出已复制")},children:"复制输出"}),e.jsx(d,{variant:"ghost",size:"sm",icon:S,onClick:D,children:"清空"})]})]}),l?e.jsx("div",{ref:R,className:"p-4 bg-gray-900 rounded-xl min-h-[100px] max-h-[400px] overflow-y-auto",children:G(l)}):e.jsx(Y,{icon:b,title:"等待运行",description:"编写代码后点击「运行」查看结果"})]})]})]})]})}export{he as default};
