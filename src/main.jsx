import React from 'react';
import ReactDOM from 'react-dom/client';
import 'katex/dist/katex.min.css';
import './styles/lab.css';
import App from './App';
import ErrorBoundary from './components/ErrorBoundary';
import { installGlobalErrorReporting } from './lib/clientErrors';
import { applySkin } from './lib/commissar';

installGlobalErrorReporting();
applySkin();

// The outer boundary: a crash in the app shell (navigation, assistant, dialogs) shows a message instead of a blank page.
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary name="app">
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
