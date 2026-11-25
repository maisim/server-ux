Invoices and credit notes can go through the tier validation flow before being
posted. Reversing a posted invoice creates and posts a credit note immediately,
which triggers the tier validation and blocks the reversal for the users who
are not reviewers of every applicable tier.

This module makes the reversal follow the tier validation flow:

* a reviewer of an applicable tier can reverse the invoice immediately;
* the other users get a draft credit note with a validation request. Once the
  credit note is approved and posted, it is reconciled with the original
  invoice.

Credit notes created manually keep the standard tier validation flow.
