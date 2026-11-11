import { useEffect, useState } from 'react'

type HealthResponse = { status: string }
const backendUrl = import.meta.env.VITE_MAIN_BACKEND_URL ?? 'http://localhost:8000'

function App() {
  const [health, setHealth] = useState<string>('Checking backend…')

  useEffect(() => {
    fetch(`${backendUrl}/health`)
      .then(async (response) => {
        if (!response.ok) throw new Error('Backend is unavailable')
        return response.json() as Promise<HealthResponse>
      })
      .then((data) => setHealth(`Backend status: ${data.status}`))
      .catch(() => setHealth('Backend status: unavailable'))
  }, [])

  return (
    <main>
      <section>
        <p className="eyebrow">TradeStream</p>
        <h1>TradeStream Dashboard</h1>
        <p>Task 1 project setup is ready.</p>
        <p className="health" aria-live="polite">{health}</p>
      </section>
    </main>
  )
}

export default App
