import { Component, StrictMode, type ErrorInfo, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import App from "./App";

class AppErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error("SleepPilot render error", error, info); }
  render() { return this.state.error ? <main className="shell"><div className="error">Interface error: {this.state.error.message}</div></main> : this.props.children; }
}

createRoot(document.getElementById("root")!).render(
  <StrictMode><AppErrorBoundary><App /></AppErrorBoundary></StrictMode>,
);
