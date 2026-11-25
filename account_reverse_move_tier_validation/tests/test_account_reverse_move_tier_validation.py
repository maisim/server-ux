# Copyright 2026 Ctrl-a
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0)

from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged

TEST_DATE = date(2026, 1, 1)


@tagged("post_install", "-at_install")
class TestAccountReverseMoveTierValidation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        group_ids = [
            cls.env.ref("account.group_account_invoice").id,
            # Posting an invoice writes the customer company on the partner.
            cls.env.ref("base.group_partner_manager").id,
        ]
        cls.submitter = cls.env["res.users"].create(
            {
                "name": "Submitter",
                "login": "test_reverse_submitter",
                "email": "submitter@test.example.com",
                "groups_id": [(6, 0, group_ids)],
            }
        )
        cls.reviewer = cls.env["res.users"].create(
            {
                "name": "Reviewer",
                "login": "test_reverse_reviewer",
                "email": "reviewer@test.example.com",
                "groups_id": [(6, 0, group_ids)],
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Test Customer", "is_company": True}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Test Product", "list_price": 100.0}
        )

    def _create_refund_definition(self):
        return self.env["tier.definition"].create(
            {
                "model_id": self.env.ref("account.model_account_move").id,
                "definition_domain": "[('move_type', '=', 'out_refund')]",
                "reviewer_id": self.reviewer.id,
            }
        )

    def _create_invoice(self, move_type="out_invoice"):
        return self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner.id,
                "invoice_date": TEST_DATE,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 100.0,
                            "tax_ids": [(6, 0, [])],
                        },
                    )
                ],
            }
        )

    def _post_invoice(self):
        invoice = self._create_invoice()
        invoice.with_user(self.submitter).action_post()
        self.assertEqual(invoice.state, "posted")
        return invoice

    def _create_reversal(self, invoice, user, refund_method="cancel"):
        return (
            self.env["account.move.reversal"]
            .with_user(user)
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "move_ids": [(6, 0, invoice.ids)],
                    "journal_id": invoice.journal_id.id,
                    "company_id": invoice.company_id.id,
                    "refund_method": refund_method,
                    "date": TEST_DATE,
                    "reason": "Reversal test",
                }
            )
        )

    def test_reversal_by_reviewer_posts_and_reconciles(self):
        """A tier reviewer reverses immediately, without a new validation."""
        self._create_refund_definition()
        invoice = self._post_invoice()
        self._create_reversal(invoice, self.reviewer).reverse_moves()
        credit_note = invoice.reversal_move_id
        self.assertEqual(len(credit_note), 1)
        self.assertEqual(credit_note.move_type, "out_refund")
        self.assertEqual(credit_note.state, "posted")
        self.assertFalse(credit_note.review_ids)
        self.assertFalse(credit_note.deferred_reversal)
        self.assertEqual(invoice.payment_state, "reversed")

    def test_reversal_by_non_reviewer_defers_until_validation(self):
        """A non-reviewer gets a draft credit note and a validation request."""
        self._create_refund_definition()
        invoice = self._post_invoice()
        self._create_reversal(invoice, self.submitter).reverse_moves()
        credit_note = invoice.reversal_move_id
        self.assertEqual(credit_note.state, "draft")
        self.assertTrue(credit_note.deferred_reversal)
        self.assertEqual(credit_note.validation_status, "pending")
        self.assertEqual(credit_note.review_ids.mapped("status"), ["pending"])
        self.assertNotEqual(invoice.payment_state, "reversed")
        with self.assertRaises(ValidationError), self.cr.savepoint():
            credit_note.with_user(self.submitter)._post()
        credit_note.with_user(self.reviewer).validate_tier()
        self.assertEqual(credit_note.validation_status, "validated")
        credit_note.with_user(self.submitter).action_post()
        self.assertEqual(credit_note.state, "posted")
        self.assertFalse(credit_note.deferred_reversal)
        self.assertEqual(invoice.payment_state, "reversed")

    def test_reversal_without_definition_completes_immediately(self):
        """Without an applicable tier, the reversal keeps the core behaviour."""
        invoice = self._post_invoice()
        self._create_reversal(invoice, self.submitter).reverse_moves()
        credit_note = invoice.reversal_move_id
        self.assertEqual(credit_note.state, "posted")
        self.assertFalse(credit_note.deferred_reversal)
        self.assertFalse(credit_note.review_ids)
        self.assertEqual(invoice.payment_state, "reversed")

    def test_reverse_cancel_skip_is_reserved_to_reviewers(self):
        """The reversal bypass only applies to the tier reviewers."""
        self._create_refund_definition()
        credit_note = self._create_invoice(move_type="out_refund")
        vals = {"state": "posted"}
        self.assertFalse(
            credit_note.with_user(self.reviewer)
            .with_context(move_reverse_cancel=True)
            ._check_state_conditions(vals)
        )
        self.assertTrue(
            credit_note.with_user(self.submitter)
            .with_context(move_reverse_cancel=True)
            ._check_state_conditions(vals)
        )
        self.assertTrue(
            credit_note.with_user(self.reviewer)._check_state_conditions(vals)
        )
