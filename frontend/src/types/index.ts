export type UserRole = 'admin' | 'restaurant' | 'galley'

export interface AppUser {
  uid: string
  email: string
  username: string
  role: UserRole
}

export interface Venue {
  id: string
  name: string
  breakfast_available: boolean
  lunch_available: boolean
  dinner_available: boolean
}

export interface Allergy {
  id: string
  name: string
}

export interface Guest {
  id: string
  cabin_number: string
  first_name: string
  last_name: string
}

export interface Voyage {
  id: string
  code: string
  start_date: string
  end_date: string
  notes?: string
  is_current: boolean
  created_at: string
}

export type TimeSlot = 'Breakfast' | 'Lunch' | 'Dinner'
export type GalleySection = 'Hot' | 'Cold' | 'Pastry'

export interface Preorder {
  id: string
  manager: string
  cabin_number: string
  guest_name: string
  dish: string
  pax: number
  allergy_notes: string
  special_requests: string
  service_time_slot: TimeSlot
  galley_section: GalleySection
  standing_order: boolean
  venue_id: string
  service_date: string
  chef_flag: boolean
  chef_remark: string
  created_at: string
  updated_at: string
}

export interface AppConfig {
  current_voyage_id: string
  cutoff_hour: number
  service_timezone: string
}

export interface ImportMapping {
  cabin_col: string
  first_name_col: string
  last_name_col: string
}
