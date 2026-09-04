from typing import List, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.device import Device


class DeviceRepository:

    @staticmethod
    def get_device_by_id(db: Session, device_id: int) -> Optional[Device]:
        return (
            db.query(Device)
            .filter(Device.id == device_id)
            .first()
        )

    @staticmethod
    def get_device_by_serial(db: Session, serial_number: str) -> Optional[Device]:
        return (
            db.query(Device)
            .filter(Device.serial_number == serial_number)
            .first()
        )

    @staticmethod
    def get_by_serial(db: Session, serial_number: str) -> Optional[Device]:
        """Alias for get_device_by_serial, used by services."""
        return DeviceRepository.get_device_by_serial(db, serial_number)

    @staticmethod
    def get_device_by_uuid(db: Session, device_uuid: str) -> Optional[Device]:
        return (
            db.query(Device)
            .filter(Device.device_uuid == device_uuid)
            .first()
        )

    @staticmethod
    def get_device_by_token_hash(db: Session, token_hash: str) -> Optional[Device]:
        return (
            db.query(Device)
            .filter(Device.device_token_hash == token_hash)
            .first()
        )

    @staticmethod
    def list_devices(db: Session) -> List[Device]:
        return db.query(Device).order_by(Device.id).all()

    @staticmethod
    def create_device(db: Session, device: Device) -> Device:
        db.add(device)
        try:
            db.commit()
            db.refresh(device)
        except SQLAlchemyError:
            db.rollback()
            raise
        return device

    @staticmethod
    def update_device(db: Session, device: Device) -> Device:
        try:
            db.commit()
            db.refresh(device)
        except SQLAlchemyError:
            db.rollback()
            raise
        return device

    @staticmethod
    def delete_device(db: Session, device: Device) -> None:
        db.delete(device)
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise
