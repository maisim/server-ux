To use this module, you need to:

#. Install it along with ``account_move_tier_validation`` and configure tier
   definitions on invoices and credit notes.
#. Reverse a posted invoice:

   * as a reviewer of an applicable tier, the credit note is posted and
     reconciled immediately;
   * as another user, a draft credit note is created and its validation is
     requested. Once approved, posting the credit note reconciles it with the
     original invoice.

A credit note created manually keeps the standard tier validation flow.
