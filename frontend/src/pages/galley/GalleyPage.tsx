import { useEffect, useState } from 'react'
import { doc, updateDoc, serverTimestamp } from 'firebase/firestore'
import { db } from '@/firebase'
import { useAppConfig } from '@/hooks/useAppConfig'
import { useOrders } from '@/hooks/useOrders'
import { getVenues } from '@/lib/api'
import { todayIso } from '@/lib/utils'
import type { Venue, TimeSlot, GalleySection } from '@/types'
import { Flag, MessageSquare } from 'lucide-react'

const TIMESLOTS: TimeSlot[] = ['Breakfast', 'Lunch', 'Dinner']
const SECTIONS: GalleySection[] = ['Hot', 'Cold', 'Pastry']

export default function GalleyPage() {
  const { config } = useAppConfig()
  const [venues, setVenues] = useState<Venue[]>([])
  const [selectedVenueId, setSelectedVenueId] = useState('')
  const [serviceDate, setServiceDate] = useState(todayIso(config?.cutoff_hour))
  const [timeSlot, setTimeSlot] = useState<TimeSlot | ''>('')
  const [section, setSection] = useState<GalleySection | ''>('')
  const [remarkDraft, setRemarkDraft] = useState<Record<string, string>>({})

  const voyageId = config?.current_voyage_id ?? ''
  const { orders, loading } = useOrders({
    voyageId,
    venueId: selectedVenueId || undefined,
    serviceDate,
    timeSlot: timeSlot || undefined,
  })

  useEffect(() => {
    getVenues().then((v) => {
      setVenues(v)
      if (v.length > 0) setSelectedVenueId(v[0].id)
    })
  }, [])

  const filteredOrders = section ? orders.filter((o) => o.galley_section === section) : orders

  const updateChefFields = async (preorderId: string, flag: boolean, remark: string) => {
    await updateDoc(doc(db, 'voyages', voyageId, 'preorders', preorderId), {
      chef_flag: flag,
      chef_remark: remark,
      updated_at: serverTimestamp(),
    })
  }

  return (
    <div className="p-6">
      <h2 className="text-xl font-bold text-gray-800 mb-5">Galley Board</h2>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <select className="input w-44" value={selectedVenueId} onChange={(e) => setSelectedVenueId(e.target.value)}>
          <option value="">All venues</option>
          {venues.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
        </select>

        <input type="date" className="input" value={serviceDate} onChange={(e) => setServiceDate(e.target.value)} />

        <select className="input" value={timeSlot} onChange={(e) => setTimeSlot(e.target.value as TimeSlot | '')}>
          <option value="">All time slots</option>
          {TIMESLOTS.map((t) => <option key={t}>{t}</option>)}
        </select>

        <select className="input" value={section} onChange={(e) => setSection(e.target.value as GalleySection | '')}>
          <option value="">All sections</option>
          {SECTIONS.map((s) => <option key={s}>{s}</option>)}
        </select>
      </div>

      {loading ? (
        <div className="text-gray-400 text-sm">Loading…</div>
      ) : filteredOrders.length === 0 ? (
        <div className="text-gray-400 text-sm">No orders match the current filters.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-100 text-left">
                {['Cabin', 'Guest', 'Dish', 'Pax', 'Allergies', 'Requests', 'Slot', 'Section', 'STD', 'Flag', 'Remark'].map((h) => (
                  <th key={h} className="px-3 py-2 font-medium text-gray-600 border-b">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredOrders.map((o) => (
                <tr key={o.id} className={`border-b hover:bg-gray-50 ${o.chef_flag ? 'bg-amber-50' : ''}`}>
                  <td className="px-3 py-2 font-medium">{o.cabin_number}</td>
                  <td className="px-3 py-2">{o.guest_name}</td>
                  <td className="px-3 py-2 font-semibold">{o.dish}</td>
                  <td className="px-3 py-2">{o.pax}</td>
                  <td className="px-3 py-2 text-red-600 text-xs font-medium">{o.allergy_notes || '—'}</td>
                  <td className="px-3 py-2 text-gray-500 text-xs">{o.special_requests || '—'}</td>
                  <td className="px-3 py-2">{o.service_time_slot}</td>
                  <td className="px-3 py-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      o.galley_section === 'Hot' ? 'bg-red-100 text-red-700' :
                      o.galley_section === 'Cold' ? 'bg-blue-100 text-blue-700' :
                      'bg-purple-100 text-purple-700'
                    }`}>
                      {o.galley_section}
                    </span>
                  </td>
                  <td className="px-3 py-2">{o.standing_order ? '★' : ''}</td>
                  <td className="px-3 py-2">
                    <button
                      onClick={() => updateChefFields(o.id, !o.chef_flag, o.chef_remark)}
                      className={`p-1 rounded transition-colors ${o.chef_flag ? 'text-amber-500 hover:text-amber-600' : 'text-gray-300 hover:text-amber-400'}`}
                      title="Toggle flag"
                    >
                      <Flag size={15} />
                    </button>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex gap-1">
                      <input
                        className="input text-xs py-0.5 px-2 w-32"
                        placeholder="Remark…"
                        value={remarkDraft[o.id] ?? o.chef_remark}
                        onChange={(e) => setRemarkDraft((d) => ({ ...d, [o.id]: e.target.value }))}
                        onBlur={() => {
                          const remark = remarkDraft[o.id] ?? o.chef_remark
                          updateChefFields(o.id, o.chef_flag, remark)
                        }}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
