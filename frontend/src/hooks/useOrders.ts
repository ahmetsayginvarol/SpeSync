import { useEffect, useState } from 'react'
import {
  collection,
  query,
  where,
  onSnapshot,
  orderBy,
  QueryConstraint,
} from 'firebase/firestore'
import { db } from '@/firebase'
import type { Preorder } from '@/types'

interface UseOrdersOptions {
  voyageId: string
  venueId?: string
  serviceDate?: string
  timeSlot?: string
}

export function useOrders({ voyageId, venueId, serviceDate, timeSlot }: UseOrdersOptions) {
  const [orders, setOrders] = useState<Preorder[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!voyageId) return

    const constraints: QueryConstraint[] = [orderBy('created_at', 'asc')]

    if (venueId) constraints.push(where('venue_id', '==', venueId))
    if (serviceDate) constraints.push(where('service_date', '==', serviceDate))
    if (timeSlot) constraints.push(where('service_time_slot', '==', timeSlot))

    const q = query(collection(db, 'voyages', voyageId, 'preorders'), ...constraints)

    const unsubscribe = onSnapshot(
      q,
      (snapshot) => {
        const items: Preorder[] = snapshot.docs.map((d) => ({
          id: d.id,
          ...(d.data() as Omit<Preorder, 'id'>),
        }))
        setOrders(items)
        setLoading(false)
      },
      (err) => {
        setError(err.message)
        setLoading(false)
      }
    )

    return unsubscribe
  }, [voyageId, venueId, serviceDate, timeSlot])

  return { orders, loading, error }
}
