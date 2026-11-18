import React from 'react';
import { isChunkLoadError, reloadForChunkError, reportClientError } from '../lib/clientErrors';

/**
 * Catches a render error in one workspace so the rest of the app (the navigation, the other tabs) keeps working.
 * App.jsx keys it by the open workspace, so switching tabs clears the error. `quiet`: show nothing instead of the
 * message (an optional card on a page that works without it). `name`: which view this is, for the report.
 * Every crash is reported to POST /api/client-errors (kept in logs/client_errors.log) and shown with its message.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null, info: '', copied: false };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    const componentStack = String(info?.componentStack || '');
    console.error('[andedu] this view failed to render:', error, componentStack);
    this.setState({ info: componentStack });
    reportClientError(this.props.name || 'view', error, componentStack);
    if (isChunkLoadError(error)) reloadForChunkError();  // stale code files: one reload fixes it
  }

  copy = () => {
    const { error, info } = this.state;
    const text = `${this.props.name || 'view'}: ${error?.message || error}\n${error?.stack || ''}\n${info}`;
    navigator.clipboard?.writeText(text).then(() => this.setState({ copied: true }), () => {});
  };

  render() {
    const { error, info, copied } = this.state;
    if (!error) return this.props.children;
    if (this.props.quiet) return null;
    const where = (info.match(/at (\w+)/) || [])[1];
    if (isChunkLoadError(error)) {
      return (
        <div className="page">
          <div className="notice notice-info stack-sm" role="alert">
            <strong>This page could not load: &amp;.edu was updated or restarted while it was open.</strong>
            <span>Reload to get the current version. Your work is saved on the server.</span>
            <div className="btn-row">
              <button type="button" className="btn btn-primary btn-sm" onClick={() => window.location.reload()}>Reload</button>
            </div>
          </div>
        </div>
      );
    }
    return (
      <div className="page">
        <div className="notice notice-bad stack-sm" role="alert">
          <strong>This page ran into a problem and could not be shown.</strong>
          <span>{this.props.name === 'app'
            ? 'Try again, or reload the page. The details were saved for fixing.'
            : 'The rest of &.edu still works: try again, or open another tab. The details were saved for fixing.'}</span>
          <details>
            <summary>What went wrong</summary>
            <p className="hint" style={{ fontFamily: 'var(--font-mono, monospace)', whiteSpace: 'pre-wrap' }}>
              {String(error?.message || error)}{where ? `\n(in ${where})` : ''}
            </p>
          </details>
          <div className="btn-row">
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => this.setState({ error: null, info: '', copied: false })}>Try again</button>
            <button type="button" className="btn btn-quiet btn-sm" onClick={this.copy}>{copied ? 'Copied' : 'Copy details'}</button>
          </div>
        </div>
      </div>
    );
  }
}
