import { useEffect, useState } from 'react'
import { collection, getDocs, addDoc } from 'firebase/firestore'
import { createUserWithEmailAndPassword } from 'firebase/auth'
import { db, auth } from '@/firebase'
import { callSetUserRole } from '@/lib/api'
import type { AppUser, UserRole } from '@/types'
import { UserPlus } from 'lucide-react'

const ROLES: UserRole[] = ['admin', 'restaurant', 'galley']

export default function UsersTab() {
  const [users, setUsers] = useState<AppUser[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<UserRole>('restaurant')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const loadUsers = async () => {
    setLoading(true)
    const snap = await getDocs(collection(db, 'users'))
    setUsers(snap.docs.map((d) => ({ uid: d.id, ...(d.data() as Omit<AppUser, 'uid'>) })))
    setLoading(false)
  }

  useEffect(() => { loadUsers() }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      const cred = await createUserWithEmailAndPassword(auth, email, password)
      await addDoc(collection(db, 'users'), { uid: cred.user.uid, email, username, role })
      await callSetUserRole(cred.user.uid, role)
      setShowForm(false)
      setEmail(''); setUsername(''); setPassword(''); setRole('restaurant')
      await loadUsers()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create user')
    } finally {
      setSaving(false)
    }
  }

  const handleRoleChange = async (uid: string, newRole: UserRole) => {
    await callSetUserRole(uid, newRole)
    await loadUsers()
  }

  return (
    <div className="max-w-2xl">
      <div className="flex justify-between items-center mb-4">
        <h3 className="font-semibold text-gray-700">Users</h3>
        <button onClick={() => setShowForm((s) => !s)} className="btn-primary flex items-center gap-2 text-sm">
          <UserPlus size={15} /> Add user
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="border rounded-lg p-4 mb-5 bg-gray-50 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Username</label>
              <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} required />
            </div>
            <div>
              <label className="label">Email</label>
              <input type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div>
              <label className="label">Password</label>
              <input type="password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} />
            </div>
            <div>
              <label className="label">Role</label>
              <select className="input" value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
                {ROLES.map((r) => <option key={r}>{r}</option>)}
              </select>
            </div>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex gap-2">
            <button type="submit" disabled={saving} className="btn-primary text-sm">{saving ? 'Creating…' : 'Create user'}</button>
            <button type="button" onClick={() => setShowForm(false)} className="btn-secondary text-sm">Cancel</button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="text-gray-400 text-sm">Loading…</div>
      ) : (
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-gray-100 text-left">
              {['Username', 'Email', 'Role'].map((h) => (
                <th key={h} className="px-3 py-2 font-medium text-gray-600 border-b">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.uid} className="border-b hover:bg-gray-50">
                <td className="px-3 py-2">{u.username}</td>
                <td className="px-3 py-2 text-gray-500">{u.email}</td>
                <td className="px-3 py-2">
                  <select
                    className="input text-xs py-0.5"
                    value={u.role}
                    onChange={(e) => handleRoleChange(u.uid, e.target.value as UserRole)}
                  >
                    {ROLES.map((r) => <option key={r}>{r}</option>)}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
