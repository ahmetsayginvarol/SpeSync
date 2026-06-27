import { useState } from 'react'
import UsersTab from './UsersTab'
import VenuesTab from './VenuesTab'
import VoyageTab from './VoyageTab'
import AllergiesTab from './AllergiesTab'
import ConfigTab from './ConfigTab'

const TABS = ['Users', 'Venues', 'Allergies', 'Voyage', 'Config'] as const
type Tab = typeof TABS[number]

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<Tab>('Users')

  return (
    <div className="p-6">
      <h2 className="text-xl font-bold text-gray-800 mb-5">Administration</h2>

      <div className="flex gap-1 border-b mb-6">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium rounded-t-md transition-colors ${
              activeTab === tab
                ? 'bg-white border border-b-white text-brand-600 -mb-px'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {activeTab === 'Users' && <UsersTab />}
      {activeTab === 'Venues' && <VenuesTab />}
      {activeTab === 'Allergies' && <AllergiesTab />}
      {activeTab === 'Voyage' && <VoyageTab />}
      {activeTab === 'Config' && <ConfigTab />}
    </div>
  )
}
