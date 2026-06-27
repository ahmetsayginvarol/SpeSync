import { useEffect, useState } from 'react'
import { getVenues, saveVenue, deleteVenue } from '@/lib/api'
import type { Venue } from '@/types'
import { Plus, Trash2 } from 'lucide-react'

const empty = (): Omit<Venue, 'id'> => ({
  name: '',
  breakfast_available: true,
  lunch_available: true,
  dinner_available: true,
})

export default function VenuesTab() {
  const [venues, setVenues] = useState<Venue[]>([])
  const [form, setForm] = useState(empty())
  const [editId, setEditId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = () => getVenues().then((v) => { setVenues(v); setLoading(false) })
  useEffect(() => { load() }, [])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    await saveVenue(form, editId ?? undefined)
    setForm(empty())
    setEditId(null)
    load()
  }

  const handleEdit = (v: Venue) => {
    setEditId(v.id)
    setForm({ name: v.name, breakfast_available: v.breakfast_available, lunch_available: v.lunch_available, dinner_available: v.dinner_available })
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this venue?')) return
    await deleteVenue(id)
    load()
  }

  return (
    <div className="max-w-lg">
      <h3 className="font-semibold text-gray-700 mb-4">Venues</h3>

      <form onSubmit={handleSave} className="border rounded-lg p-4 mb-5 bg-gray-50 space-y-3">
        <input className="input" placeholder="Venue name" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required />
        <div className="flex gap-4 text-sm">
          {(['breakfast_available', 'lunch_available', 'dinner_available'] as const).map((key) => (
            <label key={key} className="flex items-center gap-1.5 cursor-pointer">
              <input type="checkbox" checked={form[key]} onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.checked }))} />
              {key.replace('_available', '')}
            </label>
          ))}
        </div>
        <div className="flex gap-2">
          <button type="submit" className="btn-primary text-sm flex items-center gap-1"><Plus size={14} />{editId ? 'Update' : 'Add'} venue</button>
          {editId && <button type="button" onClick={() => { setEditId(null); setForm(empty()) }} className="btn-secondary text-sm">Cancel</button>}
        </div>
      </form>

      {loading ? <div className="text-gray-400 text-sm">Loading…</div> : (
        <div className="space-y-2">
          {venues.map((v) => (
            <div key={v.id} className="flex items-center justify-between border rounded-lg px-3 py-2 bg-white">
              <div>
                <span className="font-medium text-sm">{v.name}</span>
                <span className="ml-2 text-xs text-gray-500">
                  {[v.breakfast_available && 'B', v.lunch_available && 'L', v.dinner_available && 'D'].filter(Boolean).join(' · ')}
                </span>
              </div>
              <div className="flex gap-2">
                <button onClick={() => handleEdit(v)} className="text-xs text-brand-600 hover:underline">Edit</button>
                <button onClick={() => handleDelete(v.id)} className="text-gray-400 hover:text-red-500"><Trash2 size={14} /></button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
