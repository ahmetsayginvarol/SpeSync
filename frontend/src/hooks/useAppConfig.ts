import { useEffect, useState } from 'react'
import { doc, onSnapshot } from 'firebase/firestore'
import { db } from '@/firebase'
import type { AppConfig } from '@/types'

export function useAppConfig() {
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const unsubscribe = onSnapshot(doc(db, 'appConfig', 'settings'), (snap) => {
      if (snap.exists()) {
        setConfig(snap.data() as AppConfig)
      }
      setLoading(false)
    })
    return unsubscribe
  }, [])

  return { config, loading }
}
