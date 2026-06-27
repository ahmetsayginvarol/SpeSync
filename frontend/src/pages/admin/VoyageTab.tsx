import { useEffect, useState } from 'react'
import { getVoyages, createVoyage, updateAppConfig, uploadGuestCsv, callArchiveVoyage } from '@/lib/api'
import { useAppConfig } from '@/hooks/useAppConfig'
import type { Voyage } from '@/types'
import { Ship, Upload } from 'lucide-react'

export default function VoyageTab() {
  const { config } = useAppConfig()
  const [voyages, setVoyages] = useState<Voyage[]>([])
  const [loading, setLoading] = useState(true)
  const [code, setCode] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [csvFile, setCsvFile] = useState<File | null>(null)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [status, setStatus] = useState('')

  const load = () => getVoyages().then((v) => { setVoyages(v); setLoading(false) })
  useEffect(() => { load() }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    const ref = await createVoyage({ code, start_date: startDate, end_date: endDate, is_current: false, notes: '' })
    setCode(''); setStartDate(''); setEndDate('')
    setSaving(false)
    await load()
    setStatus(`Voyage created: ${ref.id}`)
  }

  const handleSetCurrent = async (v: Voyage) => {
    if (!confirm(`Set "${v.code}" as the active voyage?`)) return
    await updateAppConfig({ current_voyage_id: v.id })
    await load()
    setStatus(`Active voyage set to ${v.code}`)
  }

  const handleUploadCsv = async () => {
    if (!csvFile || !config?.current_voyage_id) return
    setUploading(true)
    try {
      await uploadGuestCsv(config.current_voyage_id, csvFile)
      setStatus('Guest CSV uploaded — import is running in the background.')
      setCsvFile(null)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <h3 className="font-semibold text-gray-700 mb-4">Create voyage</h3>
        <form onSubmit={handleCreate} className="border rounded-lg p-4 bg-gray-50 space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="label">Voyage code</label>
              <input className="input" placeholder="e.g. V2025-01" value={code} onChange={(e) => setCode(e.target.value)} required />
            </div>
            <div>
              <label className="label">Start date</label>
              <input type="date" className="input" value={startDate} onChange={(e) => setStartDate(e.target.value)} required />
            </div>
            <div>
              <label className="label">End date</label>
              <input type="date" className="input" value={endDate} onChange={(e) => setEndDate(e.target.value)} required />
            </div>
          </div>
          <button type="submit" disabled={saving} className="btn-primary flex items-center gap-2 text-sm">
            <Ship size={15} />{saving ? 'Creating…' : 'Create voyage'}
          </button>
        </form>
      </div>

      <div>
        <h3 className="font-semibold text-gray-700 mb-3">Import guest manifest (CSV)</h3>
        <p className="text-xs text-gray-500 mb-3">
          CSV must have columns: cabin_number, first_name, last_name. Upload triggers a Cloud Function that batch-imports guests under the active voyage.
        </p>
        <div className="flex gap-3 items-center">
          <input type="file" accept=".csv" onChange={(e) => setCsvFile(e.target.files?.[0] ?? null)} className="text-sm" />
          <button onClick={handleUploadCsv} disabled={!csvFile || uploading || !config?.current_voyage_id} className="btn-secondary flex items-center gap-2 text-sm">
            <Upload size={14} />{uploading ? 'Uploading…' : 'Upload'}
          </button>
        </div>
      </div>

      {status && <p className="text-sm text-green-700 bg-green-50 border border-green-200 rounded px-3 py-2">{status}</p>}

      <div>
        <h3 className="font-semibold text-gray-700 mb-3">All voyages</h3>
        {loading ? <div className="text-gray-400 text-sm">Loading…</div> : (
          <div className="space-y-2">
            {voyages.map((v) => (
              <div key={v.id} className={`flex items-center justify-between border rounded-lg px-3 py-2 ${config?.current_voyage_id === v.id ? 'border-brand-500 bg-brand-50' : 'bg-white'}`}>
                <div>
                  <span className="font-medium text-sm">{v.code}</span>
                  <span className="ml-2 text-xs text-gray-500">{v.start_date} → {v.end_date}</span>
                  {config?.current_voyage_id === v.id && <span className="ml-2 text-xs text-brand-600 font-semibold">ACTIVE</span>}
                </div>
                {config?.current_voyage_id !== v.id && (
                  <button onClick={() => handleSetCurrent(v)} className="text-xs text-brand-600 hover:underline">Set active</button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
