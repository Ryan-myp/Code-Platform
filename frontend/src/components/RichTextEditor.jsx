import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Underline from '@tiptap/extension-underline'
import CodeBlock from '@tiptap/extension-code-block'
// import Image from '@tiptap/extension-image'  // REMOVED: No image support
import {
  Bold,
  Italic,
  Underline as UnderlineIcon,
  Heading2,
  Heading3,
  List,
  ListOrdered,
  Code,
  Type,
} from 'lucide-react'

export default function RichTextEditor({
  value = '',
  onChange,
  placeholder = '请输入内容...',
  minHeight = 120,
}) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({ underline: false, codeBlock: false }),
      Placeholder.configure({ placeholder }),
      Underline,
      CodeBlock,
      // Image extension REMOVED to prevent base64 image uploads
    ],
    content: value || '',
    onUpdate: ({ editor }) => {
      onChange(editor.getHTML())
    },
    editorProps: {
      attributes: {
        class: 'prose prose-sm max-w-none focus:outline-none min-h-[120px]',
      },
    },
  })

  if (!editor) return null

  const toggleHeading = (level) => editor.chain().focus().toggleHeading({ level }).run()
  const toggleBold = () => editor.chain().focus().toggleBold().run()
  const toggleItalic = () => editor.chain().focus().toggleItalic().run()
  const toggleUnderline = () => editor.chain().focus().toggleUnderline().run()
  const toggleCodeBlock = () => editor.chain().focus().toggleCodeBlock().run()
  const toggleInlineCode = () => editor.chain().focus().toggleCode().run()
  const toggleBulletList = () => editor.chain().focus().toggleBulletList().run()
  const toggleOrderedList = () => editor.chain().focus().toggleOrderedList().run()

  const isActive = (cmd) => {
    try {
      return cmd()
    } catch {
      return false
    }
  }

  const ToolbarButton = ({ active, onClick, title, children }) => (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={`w-7 h-7 flex items-center justify-center rounded-lg transition-colors ${
        active
          ? 'bg-indigo-50 text-indigo-600'
          : 'text-gray-500 hover:text-gray-900 hover:bg-white hover:shadow-sm'
      }`}
    >
      {children}
    </button>
  )

  const Divider = () => <span className="w-px h-4 bg-gray-200 mx-0.5 self-center" />

  return (
    <div className="rounded-xl border border-gray-200 overflow-hidden bg-white focus-within:border-indigo-400 focus-within:ring-4 focus-within:ring-indigo-500/10 transition-all">
      <div className="flex items-center gap-0.5 px-2 py-1.5 bg-gray-50/80 border-b border-gray-100" role="toolbar" aria-label="格式化工具栏">
        <ToolbarButton
          onClick={() => toggleHeading(2)}
          title="标题 H2"
          active={isActive(() => editor.isActive('heading', { level: 2 }))}
        >
          <Heading2 className="w-4 h-4" />
        </ToolbarButton>
        <ToolbarButton
          onClick={() => toggleHeading(3)}
          title="标题 H3"
          active={isActive(() => editor.isActive('heading', { level: 3 }))}
        >
          <Heading3 className="w-4 h-4" />
        </ToolbarButton>
        <Divider />
        <ToolbarButton onClick={toggleBold} title="加粗 (Ctrl+B)" active={isActive(() => editor.isActive('bold'))}>
          <Bold className="w-4 h-4" />
        </ToolbarButton>
        <ToolbarButton onClick={toggleItalic} title="斜体 (Ctrl+I)" active={isActive(() => editor.isActive('italic'))}>
          <Italic className="w-4 h-4" />
        </ToolbarButton>
        <ToolbarButton
          onClick={toggleUnderline}
          title="下划线 (Ctrl+U)"
          active={isActive(() => editor.isActive('underline'))}
        >
          <UnderlineIcon className="w-4 h-4" />
        </ToolbarButton>
        <ToolbarButton
          onClick={toggleBulletList}
          title="无序列表"
          active={isActive(() => editor.isActive('bulletList'))}
        >
          <List className="w-4 h-4" />
        </ToolbarButton>
        <ToolbarButton
          onClick={toggleOrderedList}
          title="有序列表"
          active={isActive(() => editor.isActive('orderedList'))}
        >
          <ListOrdered className="w-4 h-4" />
        </ToolbarButton>
        <Divider />
        <ToolbarButton
          onClick={toggleCodeBlock}
          title="代码块"
          active={isActive(() => editor.isActive('codeBlock'))}
        >
          <Code className="w-4 h-4" />
        </ToolbarButton>
        <ToolbarButton onClick={toggleInlineCode} title="行内代码" active={isActive(() => editor.isActive('code'))}>
          <Type className="w-4 h-4" />
        </ToolbarButton>
      </div>
      <EditorContent editor={editor} style={{ minHeight }} className="p-4 bg-white" />
    </div>
  )
}
