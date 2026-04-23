import { Outlet } from 'react-router-dom'
import Sidenav from './components/Sidenav'

export default function App() {
  return (
    <div className="flex min-h-screen">
      <Sidenav />
      <main className="flex-1 min-w-0 p-6 md:p-10">
        <Outlet />
      </main>
    </div>
  )
}
