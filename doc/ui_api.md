# UI API (draft)

Prefix: `/api/ui_v0/`

## Devices

```
GET    /api/ui_v0/devices
GET    /api/ui_v0/devices/:device_id
```

## Device state

```
GET    /api/ui_v0/devices/:device_id/state
```

## Commands

```
POST   /api/ui_v0/devices/:device_id/commands
GET    /api/ui_v0/devices/:device_id/commands
GET    /api/ui_v0/devices/:device_id/commands/:command_id
DELETE /api/ui_v0/devices/:device_id/commands/:command_id
```

## Events

```
GET    /api/ui_v0/devices/:device_id/events
```
