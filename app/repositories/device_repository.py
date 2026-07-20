from sqlalchemy.orm import Session

from app.models.device import Device


class DeviceRepository:

    @staticmethod
    def get_by_serial(db: Session, serial_number: str):
        return (
            db.query(Device)
            .filter(Device.serial_number == serial_number)
            .first()
        )

    @staticmethod
    def create(db: Session, device: Device):
        db.add(device)
        db.commit()
        db.refresh(device)
        return device

    @staticmethod
    def update(db: Session, device: Device):
        db.commit()
        db.refresh(device)
        return device
