# toruq_branch_transfer (Odoo 18)

Separate module for branch-to-branch transfers (independent from `toruq_barcode`, which keeps the count features).

## Control panel: Inventory > تحويلات الفروع
- **المسارات والصلاحيات** (managers): one line = sender + from branch + to branch + allowed receivers. A user without a route never sees the Barcode button; the server rejects anything outside the routes. Users in a route are given the Inventory User group automatically (group "Branch Transfers: Participant").
- **لوحة الإدارة**: total stock and stock per branch (pivot/graph by location), goods in transit, transfer analysis (by branch/event/month), who sent / received / signed.
- **سجل التحويلات**, **كل تحويلات الفروع**, **تحويلات واردة لي**.

## Flow
1. Sender: Barcode > "ابدأ بتحويل المخزون": route, receiver, courier, then scan.
2. Validate => e-signature pad (required) => stock leaves the source warehouse to the Inter-warehouse transit location; a receipt is created for the receiver and he gets a pop-up.
3. Receiver: Barcode > "استلام تحويل وارد" (or menu). Scan/compare, Validate or "قبول الكل والتوقيع" => e-signature (required). Products not scanned/received are rejected with a reason (default "لم يصلني") and returned automatically to the sender warehouse.
4. Everything is logged (chatter on both documents + log model) with date, user, courier, items, quantities, reason, signed flag. Invoice photos are optional attachments on the transfer form.

## Optional
System parameter `brt.block_direct_interbranch` = `1` blocks direct internal transfers between warehouses for non Inventory Administrators.

## Not verified (Enterprise source not available)
Opening the picking in Barcode, `.o_validate_page`, saving of scanned quantities / picked flags, signature widget inside the Barcode dialog, field `company.internal_transit_location_id`. Lot/serial products are not handled. Check valuation entries of the first test with your accountant.
