import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './App.css'
import RecorderPage from './components/RecorderPage'
import HistoryPage from './components/HistoryPage'

function App() {
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'light')

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light')
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/home" replace />} />
        <Route
          path="/home"
          element={<RecorderPage theme={theme} toggleTheme={toggleTheme} />}
        />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/history/detail" element={<HistoryPage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
