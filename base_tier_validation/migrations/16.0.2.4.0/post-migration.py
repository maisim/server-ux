# Copyright 2025 OCA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def populate_validation_status_field(env):
    """Populate the validation_status field for all existing tier validation records."""
    # Query to find all tables that have the validation_status column
    # This prevents errors when the field doesn't exist in some models
    env.cr.execute(
        """
        SELECT table_name
        FROM information_schema.columns
        WHERE column_name = 'validation_status'
        AND table_schema = current_schema()
    """
    )

    tables_with_validation_status = [row[0] for row in env.cr.fetchall()]

    for table_name in tables_with_validation_status:
        try:
            # Convert table name to model name (basic conversion)
            model_name = table_name.replace("_", ".")

            # Check if the model exists in the registry
            if model_name in env.registry:
                model = env[model_name]

                # Check if it inherits from tier.validation
                if hasattr(model, "_inherit") and "tier.validation" in (
                    model._inherit
                    if isinstance(model._inherit, list)
                    else [model._inherit]
                ):
                    # Get records that need validation_status computation
                    records = env[model_name].search([])
                    if records:
                        # Compute validation_status for all records in batches
                        batch_size = 1000
                        for i in range(0, len(records), batch_size):
                            batch = records[i : i + batch_size]
                            batch._compute_validation_status()
                            env.cr.commit()

        except Exception as e:
            # Log error but continue with other models to prevent migration failure
            openupgrade.logged_query(
                env.cr,
                f"-- Warning: Could not populate validation_status for "
                f"table {table_name}: {str(e)}",
            )


@openupgrade.migrate()
def migrate(env, version):
    """Migrate validation_status field to be stored."""
    populate_validation_status_field(env)
