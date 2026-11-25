# Copyright 2026 Ctrl-a
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0)

{
    "name": "Account Reverse Move Tier Validation",
    "summary": "Defer the reversal of an invoice to the tier validation",
    "version": "16.0.1.0.0",
    "development_status": "Alpha",
    "category": "Accounting/Accounting",
    "website": "https://github.com/OCA/server-ux",
    "author": "Ctrl-a, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "images": ["static/description/icon.png"],
    "application": False,
    "installable": True,
    "depends": [
        "account_move_tier_validation",
    ],
}
