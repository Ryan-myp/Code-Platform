import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from '../App'

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />)
    expect(screen.getByText(/智能研发平台/i)).toBeInTheDocument()
  })

  it('shows navigation menu items', () => {
    render(<App />)
    expect(screen.getByText(/研发管理/i)).toBeInTheDocument()
    expect(screen.getByText(/智能体管理/i)).toBeInTheDocument()
    expect(screen.getByText(/系统配置/i)).toBeInTheDocument()
  })
})
