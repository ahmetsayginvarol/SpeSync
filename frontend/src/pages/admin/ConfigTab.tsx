import { useState } from 'react'
import { useAppConfig } from '@/hooks/useAppConfig'
import { updateAppConfig } from '@/lib/api'

export default function ConfigTab() {
  const { config, loading } = useAppConfig()
  const [cutoffHour, setCutoffHour] = useState('')
  const [timezone, setTimezone] = useState('')
  const [saving, setSaving] = useState(false)

  if (loading) return <div className="text-gray-400 text-sm">Loading…</div>

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    const updates: Record<string, unknown> = {}
    if (cutoffHour !== '') updates.cutoff_hour = Number(cutoffHour)
    if (timezone !== '') updates.service_timezone = timezone
    await updateAppConfig(updates)
    setSaving(false)
    setCutoffHour('')
    setTimezone('')
  }

  return (
    <div className="max-w-sm">
      <h3 className="font-semibold text-gray-700 mb-4">App Configuration</h3>

      <div className="border rounded-lg p-4 bg-gray-50 mb-5 text-sm space-y-1">
        <div><span className="text-gray-500">Current voyage ID:</span> <span className="font-mono">{config?.current_voyage_id || '—'}</span></div>
        <div><span className="text-gray-500">Cutoff hour:</span> {config?.cutoff_hour ?? '—'}</div>
        <div><span className="text-gray-500">Timezone:</span> {config?.service_timezone || '—'}</div>
      </div>

      <form onSubmit={handleSave} className="space-y-3">
        <div>
          <label className="label">Cutoff hour (0–23)</label>
          <input type="number" min={0} max={23} className="input" placeholder={String(config?.cutoff_hour ?? 4)} value={cutoffHour} onChange={(e) => setCutoffHour(e.target.value)} />
        </div>
        <div>
          <label className="label">Service timezone</label>
          <input className="input" placeholder={config?.service_timezone || 'e.g. Europe/Athens'} value={timezone} onChange={(e) => setTimezone(e.target.value)} />
        </div>
        <button type="submit" disabled={saving} className="btn-primary text-sm">{saving ? 'Saving…' : 'Save changes'}</button>
      </form>
    </div>
  )
}
