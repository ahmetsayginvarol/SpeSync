import jsPDF from 'jspdf'
import autoTable from 'jspdf-autotable'
import { format } from 'date-fns'
import type { Preorder, Venue } from '@/types'

export function exportOrdersPdf(
  orders: Preorder[],
  venue: Venue,
  serviceDate: string,
  exportedBy: string
) {
  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' })

  const title = `${venue.name} — Orders for ${serviceDate}`
  doc.setFontSize(14)
  doc.text(title, 14, 15)

  const columns = [
    'Manager',
    'Cabin',
    'Guest',
    'Dish',
    'Pax',
    'Allergies',
    'Requests',
    'Time Slot',
    'Section',
    'Standing',
  ]

  const rows = orders.map((o) => [
    o.manager,
    o.cabin_number,
    o.guest_name,
    o.dish,
    String(o.pax),
    o.allergy_notes || '—',
    o.special_requests || '—',
    o.service_time_slot,
    o.galley_section,
    o.standing_order ? 'Y' : '',
  ])

  autoTable(doc, {
    head: [columns],
    body: rows,
    startY: 22,
    styles: { fontSize: 8, cellPadding: 2 },
    headStyles: { fillColor: [59, 91, 219] },
    alternateRowStyles: { fillColor: [245, 247, 255] },
    didDrawPage: (data) => {
      const pageCount = (doc as unknown as { internal: { getNumberOfPages: () => number } })
        .internal.getNumberOfPages()
      doc.setFontSize(7)
      doc.text(
        `Exported by ${exportedBy} — ${format(new Date(), 'dd MMM yyyy HH:mm')}  |  Page ${data.pageNumber} of ${pageCount}`,
        14,
        doc.internal.pageSize.getHeight() - 6
      )
    },
  })

  const filename = `${venue.name.replace(/\s+/g, '_')}_${serviceDate}.pdf`
  doc.save(filename)
}
