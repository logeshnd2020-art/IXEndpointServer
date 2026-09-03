from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.installed_application import InstalledApplication
from app.repositories.installed_application_repository import (
    InstalledApplicationRepository,
)
from app.schemas.installed_application import (
    InstalledApplicationsRequest,
    InstalledApplicationsResponse,
)


class InstalledApplicationService:

    @staticmethod
    def sync_inventory(
        db: Session,
        request: InstalledApplicationsRequest,
        device: Device,
    ) -> InstalledApplicationsResponse:

        # The authenticated device token is authoritative.
        # Reject inventory claiming to belong to another serial number.
        if request.serial != device.serial_number:
            raise ValueError(
                "Inventory serial number does not match authenticated device"
            )

        now = datetime.now(timezone.utc)

        existing_apps = (
            InstalledApplicationRepository.get_all_by_device(
                db,
                device.id,
            )
        )

        # Track every application present in this inventory upload.
        seen_ids = set()

        created = 0
        updated = 0
        removed = 0

        try:
            for item in request.applications:

                app = InstalledApplicationRepository.get_by_identity(
                    db=db,
                    device_id=device.id,
                    name=item.name,
                    install_path=item.path,
                )

                if app is None:
                    app = InstalledApplication(
                        device_id=device.id,
                        name=item.name,
                        version=item.version,
                        bundle_id=item.bundle,
                        install_path=item.path,
                        first_seen=now,
                        last_seen=now,
                        is_installed=True,
                    )

                    InstalledApplicationRepository.add(
                        db,
                        app,
                    )

                    # Flush so the new row receives its database ID
                    # before we add it to seen_ids.
                    db.flush()

                    seen_ids.add(app.id)

                    created += 1

                else:
                    seen_ids.add(app.id)

                    changed = False

                    if app.version != item.version:
                        app.version = item.version
                        changed = True

                    if app.bundle_id != item.bundle:
                        app.bundle_id = item.bundle
                        changed = True

                    if app.install_path != item.path:
                        app.install_path = item.path
                        changed = True

                    if not app.is_installed:
                        app.is_installed = True
                        changed = True

                    app.last_seen = now

                    if changed:
                        updated += 1

            # Anything previously known but absent from the
            # current complete inventory is considered removed.
            for app in existing_apps:

                if app.id not in seen_ids and app.is_installed:
                    app.is_installed = False
                    removed += 1

            db.commit()

        except Exception:
            db.rollback()
            raise

        return InstalledApplicationsResponse(
            status="success",
            received=len(request.applications),
            created=created,
            updated=updated,
            removed=removed,
        )
