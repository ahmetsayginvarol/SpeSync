import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/utils'
import { LogOut, UtensilsCrossed, ChefHat, Settings, FileText } from 'lucide-react'

const navItems = [
  { to: '/restaurant', label: 'Restaurant', icon: UtensilsCrossed, roles: ['admin', 'restaurant'] },
  { to: '/galley', label: 'Galley Board', icon: ChefHat, roles: ['admin', 'galley'] },
  { to: '/reports', label: 'Reports', icon: FileText, roles: ['admin', 'restaurant', 'galley'] },
  { to: '/admin', label: 'Admin', icon: Settings, roles: ['admin'] },
] as const

export function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 bg-brand-900 text-white flex flex-col shrink-0">
        <div className="px-5 py-6 border-b border-brand-700">
          <h1 className="text-base font-bold tracking-wide leading-tight">Nocturne Pre-Order Management</h1>
          <p className="text-xs text-brand-100 mt-0.5 truncate">{user?.username}</p>
          <span className="inline-block mt-1 text-[10px] uppercase tracking-widest bg-brand-700 rounded px-1.5 py-0.5">
            {user?.role}
          </span>
        </div>

        <nav className="flex-1 py-4 space-y-1 px-2">
          {navItems
            .filter((item) => user && (item.roles as readonly string[]).includes(user.role))
            .map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
                    isActive
                      ? 'bg-brand-600 text-white'
                      : 'text-brand-100 hover:bg-brand-700 hover:text-white'
                  )
                }
              >
                <Icon size={16} />
                {label}
              </NavLink>
            ))}
        </nav>

        <div className="p-3 border-t border-brand-700">
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-sm text-brand-100 hover:text-white w-full px-3 py-2 rounded-md hover:bg-brand-700 transition-colors"
          >
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-gray-50">
        <Outlet />
      </main>
    </div>
  )
}
