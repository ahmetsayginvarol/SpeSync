import { useEffect, useState, useCallback } from 'react'
import { format } from 'date-fns'
import { serverTimestamp } from 'firebase/firestore'
import { useAuth } from '@/context/AuthContext'
import { useAppConfig } from '@/hooks/useAppConfig'
import { useOrders } from '@/hooks/useOrders'
import { getVenues, getAllergies, getGuests, createPreorder, updatePreorder, deletePreorder } from '@/lib/api'
import { todayIso } from '@/lib/utils'
import type { Venue, Allergy, Guest, Preorder, TimeSlot, GalleySection } from '@/types'
import { Plus, Trash2, Send, Star } from 'lucide-react'

const TIMESLOTS: TimeSlot[] = ['Breakfast', 'Lunch', 'Dinner']
const SECTIONS: GalleySection[] = ['Hot', 'Cold', 'Pastry']

interface TempOrder {
  dish: string
  pax: number
  allergy_ids: string[]
  special_requests: string
  galley_section: GalleySection
  standing_order: boolean
}

export default function RestaurantPage() {
  const { user } = useAuth()
  const { config } = useAppConfig()

  // State
  const [venues, setVenues] = useState<Venue[]>([])
  const [allergies, setAllergies] = useState<Allergy[]>([])
  const [selectedVenue, setSelectedVenue] = useState<Venue | null>(null)
  const [serviceDate, setServiceDate] = useState(todayIso(config?.cutoff_hour))
  const [timeSlot, setTimeSlot] = useState<TimeSlot>('Dinner')

  // Cabin / guest
  const [cabinInput, setCabinInput] = useState('')
  const [guests, setGuests] = useState<Guest[]>([])
  const [selectedGuest, setSelectedGuest] = useState<Guest | null>(null)

  // Temp order being built
  const [dish, setDish] = useState('')
  const [pax, setPax] = useState(1)
  const [selectedAllergies, setSelectedAllergies] = useState<string[]>([])
  const [specialRequests, setSpecialRequests] = useState('')
  const [galleySection, setGalleySection] = useState<GalleySection>('Hot')
  const [standingOrder, setStandingOrder] = useState(false)
  const [tempOrders, setTempOrders] = useState<TempOrder[]>([])

  const voyageId = config?.current_voyage_id ?? ''
  const { orders, loading: ordersLoading } = useOrders({
    voyageId,
    venueId: selectedVenue?.id,
    serviceDate,
  })

  useEffect(() => {
    getVenues().then((v) => {
      setVenues(v)
      if (v.length > 0) setSelectedVenue(v[0])
    })
    getAllergies().then(setAllergies)
  }, [])

  const lookupCabin = useCallback(async () => {
    if (!voyageId || !cabinInput.trim()) return
    const g = await getGuests(voyageId, cabinInput.trim())
    setGuests(g)
    setSelectedGuest(g.length === 1 ? g[0] : null)
  }, [voyageId, cabinInput])

  const addToTemp = () => {
    if (!dish.trim()) return
    setTempOrders((prev) => [
      ...prev,
      { dish, pax, allergy_ids: selectedAllergies, special_requests: specialRequests, galley_section: galleySection, standing_order: standingOrder },
    ])
    setDish('')
    setPax(1)
    setSelectedAllergies([])
    setSpecialRequests('')
  }

  const finaliseOrders = async () => {
    if (!selectedGuest || !selectedVenue || !voyageId || tempOrders.length === 0) return

    const guestName = `${selectedGuest.first_name} ${selectedGuest.last_name}`
    for (const t of tempOrders) {
      const allergyNames = allergies.filter((a) => t.allergy_ids.includes(a.id)).map((a) => a.name).join(', ')
      await createPreorder(voyageId, {
        manager: user!.username,
        cabin_number: selectedGuest.cabin_number,
        guest_name: guestName,
        dish: t.dish,
        pax: t.pax,
        allergy_notes: allergyNames,
        special_requests: t.special_requests,
        service_time_slot: timeSlot,
        galley_section: t.galley_section,
        standing_order: t.standing_order,
        venue_id: selectedVenue.id,
        service_date: serviceDate,
        chef_flag: false,
        chef_remark: '',
      })
    }
    setTempOrders([])
    setCabinInput('')
    setGuests([])
    setSelectedGuest(null)
  }

  const toggleAllergy = (id: string) => {
    setSelectedAllergies((prev) => prev.includes(id) ? prev.filter((a) => a !== id) : [...prev, id])
  }

  return (
    <div className="flex h-full">
      {/* Left panel — order entry */}
      <div className="w-96 shrink-0 border-r bg-white flex flex-col overflow-y-auto">
        <div className="px-5 py-4 border-b">
          <h2 className="font-semibold text-gray-800">New Pre-Order</h2>
        </div>

        <div className="p-5 space-y-4 flex-1">
          {/* Venue */}
          <div>
            <label className="label">Venue</label>
            <select
              className="input"
              value={selectedVenue?.id ?? ''}
              onChange={(e) => setSelectedVenue(venues.find((v) => v.id === e.target.value) ?? null)}
            >
              {venues.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>
          </div>

          {/* Service date + timeslot */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Date</label>
              <input type="date" className="input" value={serviceDate} onChange={(e) => setServiceDate(e.target.value)} />
            </div>
            <div>
              <label className="label">Time Slot</label>
              <select className="input" value={timeSlot} onChange={(e) => setTimeSlot(e.target.value as TimeSlot)}>
                {TIMESLOTS.map((t) => <option key={t}>{t}</option>)}
              </select>
            </div>
          </div>

          {/* Cabin lookup */}
          <div>
            <label className="label">Cabin</label>
            <div className="flex gap-2">
              <input
                className="input flex-1"
                placeholder="Cabin number"
                value={cabinInput}
                onChange={(e) => setCabinInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && lookupCabin()}
              />
              <button onClick={lookupCabin} className="btn-secondary text-sm px-3">Find</button>
            </div>
          </div>

          {/* Guest selection */}
          {guests.length > 0 && (
            <div>
              <label className="label">Guest</label>
              <div className="space-y-1">
                {guests.map((g) => (
                  <label key={g.id} className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="radio"
                      name="guest"
                      checked={selectedGuest?.id === g.id}
                      onChange={() => setSelectedGuest(g)}
                    />
                    {g.first_name} {g.last_name}
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Dish */}
          <div>
            <label className="label">Dish</label>
            <input className="input" placeholder="Dish name" value={dish} onChange={(e) => setDish(e.target.value)} />
          </div>

          {/* Pax + section */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Pax</label>
              <input type="number" min={1} className="input" value={pax} onChange={(e) => setPax(Number(e.target.value))} />
            </div>
            <div>
              <label className="label">Section</label>
              <select className="input" value={galleySection} onChange={(e) => setGalleySection(e.target.value as GalleySection)}>
                {SECTIONS.map((s) => <option key={s}>{s}</option>)}
              </select>
            </div>
          </div>

          {/* Allergies */}
          {allergies.length > 0 && (
            <div>
              <label className="label">Allergies</label>
              <div className="flex flex-wrap gap-2">
                {allergies.map((a) => (
                  <button
                    key={a.id}
                    onClick={() => toggleAllergy(a.id)}
                    className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                      selectedAllergies.includes(a.id)
                        ? 'bg-red-500 text-white border-red-500'
                        : 'border-gray-300 text-gray-600 hover:border-red-400'
                    }`}
                  >
                    {a.name}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Special requests */}
          <div>
            <label className="label">Special Requests</label>
            <textarea className="input" rows={2} value={specialRequests} onChange={(e) => setSpecialRequests(e.target.value)} />
          </div>

          {/* Standing order */}
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={standingOrder} onChange={(e) => setStandingOrder(e.target.checked)} />
            <Star size={14} className={standingOrder ? 'text-amber-500' : 'text-gray-400'} />
            Standing order (repeats daily)
          </label>

          {/* Add to temp list */}
          <button onClick={addToTemp} disabled={!dish.trim()} className="btn-secondary w-full flex items-center justify-center gap-2">
            <Plus size={16} /> Add dish to order
          </button>

          {/* Temp list */}
          {tempOrders.length > 0 && (
            <div className="border rounded-lg divide-y text-sm">
              {tempOrders.map((t, i) => (
                <div key={i} className="flex items-center justify-between px-3 py-2">
                  <div>
                    <span className="font-medium">{t.dish}</span>
                    <span className="text-gray-500 ml-2">×{t.pax} · {t.galley_section}</span>
                    {t.standing_order && <span className="ml-2 text-amber-500 text-xs">STD</span>}
                  </div>
                  <button onClick={() => setTempOrders((p) => p.filter((_, j) => j !== i))} className="text-gray-400 hover:text-red-500">
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Finalise */}
          <button
            onClick={finaliseOrders}
            disabled={!selectedGuest || tempOrders.length === 0}
            className="btn-primary w-full flex items-center justify-center gap-2"
          >
            <Send size={16} /> Save order
          </button>
        </div>
      </div>

      {/* Right panel — orders list */}
      <div className="flex-1 overflow-auto p-6">
        <h2 className="font-semibold text-gray-800 mb-4">
          Orders — {selectedVenue?.name ?? 'All Venues'} — {serviceDate}
        </h2>

        {ordersLoading ? (
          <div className="text-gray-400 text-sm">Loading orders…</div>
        ) : orders.length === 0 ? (
          <div className="text-gray-400 text-sm">No orders yet for this date and venue.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-gray-100 text-left">
                  {['Manager', 'Cabin', 'Guest', 'Dish', 'Pax', 'Allergies', 'Requests', 'Slot', 'Section', 'STD', 'Chef'].map((h) => (
                    <th key={h} className="px-3 py-2 font-medium text-gray-600 border-b">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id} className={`border-b hover:bg-gray-50 ${o.chef_flag ? 'bg-amber-50' : ''}`}>
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
                    <td className="px-3 py-2 text-xs text-amber-700">{o.chef_remark || ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
