import React from 'react';

/**
 * Catches a render error in one workspace so the rest of the app (the navigation, the other tabs) keeps working.
 * App.jsx keys it by the open workspace, so switching tabs clears the error. `quiet`: show nothing instead of the
 * message (an optional card on a page that works without it).
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('[andedu] this view failed to render:', error, info?.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    if (this.props.quiet) return null;
    return (
      <div className="page">
        <div className="notice notice-bad stack-sm" role="alert">
          <strong>This page ran into a problem and could not be shown.</strong>
          <span>The rest of &amp;.edu still works: try again, or open another tab.</span>
          <div className="btn-row">
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => this.setState({ error: null })}>Try again</button>
          </div>
        </div>
      </div>
    );
  }
}
