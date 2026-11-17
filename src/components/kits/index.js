import { lazy } from 'react';
import '../../styles/kit_tools.css';

export { runKitTool } from './kitTool';

/** Kit id -> its Tools desk (one lazy chunk each). */
export const KIT_TOOLS = {
  polity: lazy(() => import('./PolityDesk')),
  music: lazy(() => import('./MusicDesk')),
  classics: lazy(() => import('./ClassicsDesk')),
  literature: lazy(() => import('./LiteratureDesk')),
  rhetoric: lazy(() => import('./RhetoricDesk')),
  art_history: lazy(() => import('./ArtHistoryDesk')),
};
