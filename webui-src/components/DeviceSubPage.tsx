import type { ReactNode } from 'react';
import { BreadCrumb } from 'primereact/breadcrumb';
import type { MenuItem, MenuItemOptions } from 'primereact/menuitem';
import { Link } from 'wouter';

function linkTemplate(to: string, label: string) {
  return (_item: MenuItem, options: MenuItemOptions) => (
    <Link to={to} className={options.className}>
      <span className={options.labelClassName}>{label}</span>
    </Link>
  );
}

export function DeviceSubPage({
  deviceId,
  title,
  children,
}: {
  deviceId: string;
  title?: string;
  children: ReactNode;
}) {
  const items: MenuItem[] = [
    { label: 'Devices', template: linkTemplate('/devices', 'Devices') },
  ];
  if (title) {
    items.push({
      label: deviceId,
      template: linkTemplate(`/devices/${deviceId}`, deviceId),
    });
    items.push({ label: title });
  } else {
    items.push({ label: deviceId });
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <BreadCrumb model={items} />
      {children}
    </div>
  );
}
