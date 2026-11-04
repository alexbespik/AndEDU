import React, { useEffect, useRef, useState } from 'react';
import { ChevronDown, LogOut, Wifi, WifiOff } from 'lucide-react';
import ThemeSwitch from './ThemeSwitch';

/** One button for the account: name, theme, connection and sign out live in its menu. */
export default function AccountMenu({ user, online, onSignOut }) {
  const [open, setOpen] = useState(false);
  const wrap = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (!wrap.current?.contains(e.target)) setOpen(false); };
    const esc = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc); };
  }, [open]);

  if (!user) return null;
  const initial = (user.name || '?').trim().charAt(0).toUpperCase();
  return (
    <div className="account" ref={wrap}>
      <button type="button" className="account-btn" aria-haspopup="true" aria-expanded={open} onClick={() => setOpen((o) => !o)}
        title={online ? user.name : `${user.name} · backend offline`}>
        <span className="avatar" aria-hidden="true">{initial}<span className="avatar-dot" data-online={online} /></span>
        <span className="account-name">{user.name}</span>
        <ChevronDown size={14} aria-hidden="true" />
      </button>
      {open && (
        <div className="account-menu" role="menu">
          <div className="account-head">
            <span className="avatar avatar-lg" aria-hidden="true">{initial}</span>
            <div>
              <strong>{user.name}</strong>
              <span className="hint">{user.local === false ? 'Account' : 'Profile on this computer'}</span>
            </div>
          </div>
          <div className="account-row">
            <span className="hint">Theme</span>
            <ThemeSwitch />
          </div>
          <div className="account-row" role="status">
            <span className="hint">Server</span>
            <span className="conn-pill" data-state={online ? 'online' : 'offline'}>
              {online ? <Wifi size={13} aria-hidden="true" /> : <WifiOff size={13} aria-hidden="true" />} {online ? 'Connected' : 'Offline'}
            </span>
          </div>
          <button type="button" role="menuitem" className="account-signout" onClick={() => { setOpen(false); onSignOut(); }}>
            <LogOut size={15} aria-hidden="true" /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}
