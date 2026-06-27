import { useEffect, useState } from 'react'
import { useAppConfig } from '@/hooks/useAppConfig'
import { useOrders } from '@/hooks/useOrders'
import { getVenues } from '@/lib/api'
import { exportOrdersPdf } from '@/lib/pdf'
import { useAuth } from '@/context/AuthContext'
import { todayIso } from '@/lib/utils'
import type { Venue } from '@/types'
import { Download } from 'lucide-react'

export default function ReportsPage() {
  const { user } = useAuth()
  const { config } = useAppConfig()
  const [venues, setVenues] = useState<Venue[]>([])
  const [selectedVenue, setSelectedVenue] = useState<Venue | null>(null)
  const [serviceDate, setServiceDate] = useState(todayIso(config?.cutoff_hour))

  const voyageId = config?.current_voyage_id ?? ''
  const { orders, loading } = useOrders({
    voyageId,
    venueId: selectedVenue?.id,
    serviceDate,
  })

  useEffect(() => {
    getVenues().then((v) => {
      setVenues(v)
      if (v.length > 0) setSelectedVenue(v[0])
    })
  }, [])

  const handleExport = () => {
    if (!selectedVenue) return
    exportOrdersPdf(orders, selectedVenue, serviceDate, user?.username ?? '')
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-xl font-bold text-gray-800">Reports</h2>
        <button
          onClick={handleExport}
          disabled={orders.length === 0}
          className="btn-primary flex items-center gap-2"
        >
          <Download size={16} /> Export PDF
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-6">
        <select
          className="input w-48"
          value={selectedVenue?.id ?? ''}
          onChange={(e) => setSelectedVenue(venues.find((v) => v.id === e.target.value) ?? null)}
        >
          {venues.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
        </select>
        <input type="date" className="input" value={serviceDate} onChange={(e) => setServiceDate(e.target.value)} />
      </div>

      {/* Preview table */}
      {loading ? (
        <div className="text-gray-400 text-sm">Loading…</div>
      ) : orders.length === 0 ? (
        <div className="text-gray-400 text-sm">No orders found for the selected filters.</div>
      ) : (
        <>
          <p className="text-sm text-gray-500 mb-3">{orders.length} order{orders.length !== 1 ? 's' : ''} found</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-gray-100 text-left">
                  {['Manager', 'Cabin', 'Guest', 'Dish', 'Pax', 'Allergies', 'Requests', 'Slot', 'Section', 'STD'].map((h) => (
                    <th key={h} className="px-3 py-2 font-medium text-gray-600 border-b">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id} className="border-b hover:bg-gray-50">
                    <td className="px-3 py-2">{o.manager}</td>
                    <td className="px-3 py-2">{o.cabin_number}</td>
                    <td className="px-3 py-2">{o.guest_name}</td>
                    <td className="px-3 py-2 font-medium">{o.dish}</td>
                    <td className="px-3 py-2">{o.pax}</td>
                    <td className="px-3 py-2 text-red-600 text-xs">{o.allergy_notes || '—'}</td>
                    <td className="px-3 py-2 text-gray-500 text-xs">{o.special_requests || '—'}</td>
                    <td className="px-3 py-2">{o.service_time_slot}</td>
                    <td className="px-3 py-2">{o.galley_section}</td>
                    <td className="px-3 py-2">{o.standing_order ? '★' : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
