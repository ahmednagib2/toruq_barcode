# toruq_barcode (Odoo 18)

Every feature has its own switch (group) in the user form, Technical section.

## Count features
Count Only / Hide Scanner Graphic / Guided Count Mode (see earlier versions; unchanged).

## Branch transfers (v18.0.3.0.0) - no accountant approval
- User field "مخزن الفرع": the user's branch warehouse (sender source, receiver branch).
- Group **Transfer Sender**: Barcode button "ابدأ بتحويل المخزون": choose destination branch, receiver (users of that branch with the Receiver group) and courier name, then scan. Validate = dispatch: stock leaves the sender warehouse to the Inter-warehouse transit location; a receipt (transit -> destination) is created for the receiver and he gets a pop-up.
- Group **Transfer Receiver**: Barcode button "استلام تحويل وارد" (or menu "تحويلات واردة لي"). Scan/compare; Validate (or "قبول الكل"). Products not scanned/received are rejected with a reason (default "لم يصلني") and returned automatically transit -> sender warehouse. Accepted ones enter the destination warehouse.
- Every dispatch / receive / reject / return is written to the transfer chatter on both documents and to Inventory > "سجل تحويلات الفروع" (managers).
- Invoice photos (both sides) are optional attachments on the transfer form. Managers see all in "تحويلات الفروع".
- The old accountant-approval group and buttons were removed.

## Limits
Lot/serial-tracked products are not handled. Check the valuation entries of the first test with your accountant.

## Not verified (Enterprise source not available)
Opening the picking in Barcode, `.o_validate_page`, saving of scanned quantities, picked flags behaviour, and the exact transit-location field (`company.internal_transit_location_id`).
