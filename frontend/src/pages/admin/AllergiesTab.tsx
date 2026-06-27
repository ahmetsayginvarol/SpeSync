import { useEffect, useState } from 'react'
import { getAllergies, saveAllergy, deleteAllergy } from '@/lib/api'
import type { Allergy } from '@/types'
import { Plus, Trash2 } from 'lucide-react'

const DEFAULTS = ['PEANUTS', 'GLUTEN', 'SHELLFISH', 'SOY', 'DAIRY', 'EGG', 'TREE NUTS']

export default function AllergiesTab() {
  const [allergies, setAllergies] = useState<Allergy[]>([])
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(true)

  const load = () => getAllergies().then((a) => { setAllergies(a); setLoading(false) })
  useEffect(() => { load() }, [])

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    await saveAllergy(name.trim().toUpperCase())
    setName('')
    load()
  }

  const handleDelete = async (id: string) => {
    await deleteAllergy(id)
    load()
  }

  const seedDefaults = async () => {
    for (const d of DEFAULTS) {
      if (!allergies.find((a) => a.name === d)) await saveAllergy(d)
    }
    load()
  }

  return (
    <div className="max-w-sm">
      <div className="flex justify-between items-center mb-4">
        <h3 className="font-semibold text-gray-700">Allergies</h3>
        {allergies.length === 0 && (
          <button onClick={seedDefaults} className="btn-secondary text-xs">Seed defaults</button>
        )}
      </div>

      <form onSubmit={handleAdd} className="flex gap-2 mb-4">
        <input className="input flex-1" placeholder="Allergy name" value={name} onChange={(e) => setName(e.target.value)} />
        <button type="submit" className="btn-primary flex items-center gap-1 text-sm"><Plus size={14} />Add</button>
      </form>

      {loading ? <div className="text-gray-400 text-sm">Loading…</div> : (
        <div className="space-y-1.5">
          {allergies.map((a) => (
            <div key={a.id} className="flex items-center justify-between border rounded px-3 py-1.5 bg-white">
              <span className="text-sm font-medium">{a.name}</span>
              <button onClick={() => handleDelete(a.id)} className="text-gray-400 hover:text-red-500"><Trash2 size={13} /></button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
