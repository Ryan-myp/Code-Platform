import React from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Home, Send, TrendingUp, Image as ImageIcon, Layers, Wand2 } from 'lucide-react'

const NAV_ITEMS = [
  { path: '/home', label: '首页', icon: Home },
  { path: '/workspace', label: 'AI工作台', icon: Wand2 },
  { path: '/publish', label: '发布', icon: Send },
  { path: '/growth', label: '增长', icon: TrendingUp },
  { path: '/image-factory', label: '生图', icon: ImageIcon },
  { path: '/templates', label: '模板', icon: Layers },
]

export default function MobileBottomNav() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-gray-200 safe-bottom">
      <div className="flex items-center justify-around h-14 px-1">
        {NAV_ITEMS.map((item) => {
          const active =
            location.pathname === item.path || location.pathname.startsWith(item.path + '/')
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={`flex flex-col items-center justify-center gap-0.5 flex-1 h-full transition-colors ${
                active ? 'text-violet-600' : 'text-gray-400 hover:text-gray-600'
              }`}
            >
              <item.icon className={`w-5 h-5 ${active ? 'stroke-[2.5px]' : ''}`} />
              <span className="text-[10px] font-medium">{item.label}</span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
