import { useEffect, useState } from 'react'

type HealthResponse = { status: string }

function App() {
  const [health, setHealth] = useState<string>('Checking backend…')

  useEffect(() => {
    fetch('http://localhost:8000/health')
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
        <p className="eyebrow">Arham Fintech</p>
        <h1>Market Dashboard</h1>
        <p>Task 1 project setup is ready.</p>
        <p className="health" aria-live="polite">{health}</p>
      </section>
    </main>
  )
}

export default App
