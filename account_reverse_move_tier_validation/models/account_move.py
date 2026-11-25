# Copyright 2026 Ctrl-a
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0)

from collections import defaultdict

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    deferred_reversal = fields.Boolean(
        copy=False,
        readonly=True,
        help="Credit note created by a reversal deferred until validation: "
        "it is posted and reconciled once approved.",
    )

    def _is_tier_reviewer(self):
        """Whether the current user reviews at least one applicable tier."""
        self.ensure_one()
        tiers = (
            self.env["tier.definition"]
            .with_context(active_test=True)
            .search(
                [
                    ("model", "=", self._name),
                    ("company_id", "in", [False] + self._get_company().ids),
                ]
            )
        )
        for definition in tiers.filtered(self.evaluate_tier):
            reviewers = definition.reviewer_id | definition.reviewer_group_id.users
            if not reviewers and definition.reviewer_field_id:
                value = getattr(self, definition.reviewer_field_id.name, False)
                if value and value._name == "res.users":
                    reviewers = value
            if self.env.user in reviewers:
                return True
        return False

    def _get_under_validation_exceptions(self):
        res = super()._get_under_validation_exceptions()
        # The reversal wizard computes the recipient bank of the draft credit
        # note after the reversal, when the deferred draft is already under
        # validation.
        if any(self.mapped("deferred_reversal")):
            res.append("partner_bank_id")
        return res

    def _check_state_conditions(self, vals):
        # Reversing a move makes the accounting core post the reversal
        # immediately with move_reverse_cancel in the context. The tier
        # reviewers may cancel this way without a new validation.
        if self.env.context.get("move_reverse_cancel") and self._is_tier_reviewer():
            return False
        return super()._check_state_conditions(vals)

    def _reverse_moves(self, default_values_list=None, cancel=False):
        # Only invoices/credit notes: entries are out of the tier validation
        # and keep the core behaviour.
        if not cancel or not all(
            move.is_invoice(include_receipts=True) for move in self
        ):
            return super()._reverse_moves(default_values_list, cancel=cancel)
        reverse_moves = super()._reverse_moves(default_values_list, cancel=False)
        if not reverse_moves:
            return reverse_moves
        reviewers = reverse_moves.filtered(lambda move: move._is_tier_reviewer())
        others = reverse_moves - reviewers
        to_validate = others.filtered("need_validation")
        to_complete = others - to_validate
        if to_validate:
            to_validate.write({"deferred_reversal": True})
            for move in to_validate:
                move.request_validation()
        immediate = reviewers | to_complete
        if immediate:
            immediate.write({"deferred_reversal": True})
            immediate.with_context(move_reverse_cancel=True)._post(soft=False)
        return reverse_moves

    def _post(self, soft=True):
        res = super()._post(soft=soft)
        self.filtered(
            lambda move: move.deferred_reversal and move.state == "posted"
        )._complete_deferred_reversal()
        return res

    def _complete_deferred_reversal(self):
        """Unreconcile the origin, then reconcile it with the posted credit note."""
        for move in self:
            original = move.reversed_entry_id
            if not original or original.state != "posted":
                continue
            original.line_ids.remove_move_reconcile()
            groups = defaultdict(list)
            for line in (original.line_ids + move.line_ids).filtered(
                lambda line: not line.reconciled
            ):
                groups[(line.account_id, line.currency_id)].append(line.id)
            for (account, _currency), line_ids in groups.items():
                if account.reconcile or account.account_type in (
                    "asset_cash",
                    "liability_credit_card",
                ):
                    self.env["account.move.line"].browse(line_ids).with_context(
                        move_reverse_cancel=True
                    ).reconcile()
            move.with_context(skip_validation_check=True).write(
                {"deferred_reversal": False}
            )
