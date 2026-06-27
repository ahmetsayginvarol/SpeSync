import {
  collection,
  doc,
  addDoc,
  updateDoc,
  deleteDoc,
  getDocs,
  getDoc,
  query,
  where,
  serverTimestamp,
  writeBatch,
} from 'firebase/firestore'
import { httpsCallable } from 'firebase/functions'
import { ref, uploadBytes } from 'firebase/storage'
import { db, functions, storage } from '@/firebase'
import type { Preorder, Venue, Allergy, Guest, Voyage, AppConfig } from '@/types'

// ── Preorders ────────────────────────────────────────────────────

export async function createPreorder(
  voyageId: string,
  data: Omit<Preorder, 'id' | 'created_at' | 'updated_at'>
) {
  return addDoc(collection(db, 'voyages', voyageId, 'preorders'), {
    ...data,
    created_at: serverTimestamp(),
    updated_at: serverTimestamp(),
  })
}

export async function updatePreorder(
  voyageId: string,
  preorderId: string,
  data: Partial<Preorder>
) {
  return updateDoc(doc(db, 'voyages', voyageId, 'preorders', preorderId), {
    ...data,
    updated_at: serverTimestamp(),
  })
}

export async function deletePreorder(voyageId: string, preorderId: string) {
  return deleteDoc(doc(db, 'voyages', voyageId, 'preorders', preorderId))
}

// ── Guests ───────────────────────────────────────────────────────

export async function getGuests(voyageId: string, cabinNumber?: string): Promise<Guest[]> {
  const col = collection(db, 'voyages', voyageId, 'guests')
  const q = cabinNumber ? query(col, where('cabin_number', '==', cabinNumber)) : col
  const snap = await getDocs(q)
  return snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<Guest, 'id'>) }))
}

// ── Venues ───────────────────────────────────────────────────────

export async function getVenues(): Promise<Venue[]> {
  const snap = await getDocs(collection(db, 'venues'))
  return snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<Venue, 'id'>) }))
}

export async function saveVenue(venue: Omit<Venue, 'id'>, id?: string) {
  if (id) {
    await updateDoc(doc(db, 'venues', id), venue)
    return id
  }
  const ref = await addDoc(collection(db, 'venues'), venue)
  return ref.id
}

export async function deleteVenue(id: string) {
  return deleteDoc(doc(db, 'venues', id))
}

// ── Allergies ────────────────────────────────────────────────────

export async function getAllergies(): Promise<Allergy[]> {
  const snap = await getDocs(collection(db, 'allergies'))
  return snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<Allergy, 'id'>) }))
}

export async function saveAllergy(name: string, id?: string) {
  if (id) {
    await updateDoc(doc(db, 'allergies', id), { name })
    return id
  }
  const ref = await addDoc(collection(db, 'allergies'), { name })
  return ref.id
}

export async function deleteAllergy(id: string) {
  return deleteDoc(doc(db, 'allergies', id))
}

// ── Voyages ──────────────────────────────────────────────────────

export async function getVoyages(): Promise<Voyage[]> {
  const snap = await getDocs(collection(db, 'voyages'))
  return snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<Voyage, 'id'>) }))
}

export async function createVoyage(data: Omit<Voyage, 'id' | 'created_at'>) {
  return addDoc(collection(db, 'voyages'), {
    ...data,
    created_at: serverTimestamp(),
  })
}

// ── App Config ───────────────────────────────────────────────────

export async function getAppConfig(): Promise<AppConfig | null> {
  const snap = await getDoc(doc(db, 'appConfig', 'settings'))
  return snap.exists() ? (snap.data() as AppConfig) : null
}

export async function updateAppConfig(data: Partial<AppConfig>) {
  return updateDoc(doc(db, 'appConfig', 'settings'), data)
}

// ── Cloud Functions ──────────────────────────────────────────────

export async function callSetUserRole(uid: string, role: string) {
  const fn = httpsCallable(functions, 'setUserRole')
  return fn({ uid, role })
}

export async function callArchiveVoyage(voyageId: string, newVoyageId: string) {
  const fn = httpsCallable(functions, 'archiveVoyage')
  return fn({ voyageId, newVoyageId })
}

export async function uploadGuestCsv(voyageId: string, file: File) {
  const storageRef = ref(storage, `imports/${voyageId}/${file.name}`)
  await uploadBytes(storageRef, file)
}
