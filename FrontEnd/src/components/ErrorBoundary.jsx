import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, message: '' };
  }

  static getDerivedStateFromError(error) {
    return {
      hasError: true,
      message: error?.message || 'Erro inesperado ao renderizar a interface.',
    };
  }

  componentDidCatch(error, info) {
    if (typeof this.props.onError === 'function') {
      this.props.onError(error, info);
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, message: '' });
    if (typeof this.props.onReset === 'function') {
      this.props.onReset();
    } else if (typeof window !== 'undefined') {
      window.location.reload();
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-bg p-6">
          <div className="w-full max-w-md rounded-lg border border-line bg-surface p-6 text-center shadow">
            <h1 className="font-display mb-2 text-lg font-semibold text-ink">
              Algo deu errado na interface
            </h1>
            <p className="mb-4 text-sm text-ink-soft">
              {this.state.message}
            </p>
            <button type="button" className="btn btn-primary" onClick={this.handleReset}>
              Recarregar painel
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
