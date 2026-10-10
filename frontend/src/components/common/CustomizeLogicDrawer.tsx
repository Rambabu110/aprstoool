import React, { useState } from "react";
import { X, Info, Check } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface CustomizeLogicDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onApply?: (config: LogicConfig) => void;
}

export interface LogicConfig {
  sources: string[];
  country: string;
  gate1Enabled: boolean;
  gate1Threshold: string;
  gate2Enabled: boolean;
  gate2Threshold: string;
  gate3Enabled: boolean;
  gate3Threshold: string;
  gate4Enabled: boolean;
  gate4Threshold: string;
  gate5Enabled: boolean;
  gate5Threshold: string;
  weights: {
    trendVelocity: number;
    demand: number;
    priceMargin: number;
    aiConfidence: number;
  };
}

const DEFAULT_CONFIG: LogicConfig = {
  sources: ["Amazon", "Flipkart", "Myntra", "Meesho", "Nykaa"],
  country: "India",
  gate1Enabled: true,
  gate1Threshold: "Top 100 ranks",
  gate2Enabled: true,
  gate2Threshold: "Min +100% rank",
  gate3Enabled: true,
  gate3Threshold: "Min 500 reviews",
  gate4Enabled: true,
  gate4Threshold: "Rs 300 - Rs 5,000",
  gate5Enabled: true,
  gate5Threshold: "Model: Verifier-2",
  weights: {
    trendVelocity: 40,
    demand: 25,
    priceMargin: 20,
    aiConfidence: 15,
  },
};

export const CustomizeLogicDrawer: React.FC<CustomizeLogicDrawerProps> = ({
  isOpen,
  onClose,
  onApply,
}) => {
  const [config, setConfig] = useState<LogicConfig>(DEFAULT_CONFIG);
  const [savedNotice, setSavedNotice] = useState(false);

  if (!isOpen) return null;

  const toggleSource = (src: string) => {
    setConfig((prev) => ({
      ...prev,
      sources: prev.sources.includes(src)
        ? prev.sources.filter((s) => s !== src)
        : [...prev.sources, src],
    }));
  };

  const handleSave = () => {
    if (onApply) {
      onApply(config);
    }
    setSavedNotice(true);
    setTimeout(() => {
      setSavedNotice(false);
      onClose();
    }, 1200);
  };

  const handleReset = () => {
    setConfig(DEFAULT_CONFIG);
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity"
        onClick={onClose}
      />

      {/* Drawer Container */}
      <div className="relative w-full max-w-md bg-white h-full shadow-2xl flex flex-col z-10 overflow-hidden animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="p-6 border-b border-slate-100 flex items-start justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900">
              Customize finding logic
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Default logic from APRS. Change it to filter and weight discovery.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Truthful Persistence Notice */}
        <div className="mx-6 mt-4 p-3 rounded-lg bg-indigo-50/60 border border-indigo-100 text-xs text-indigo-800 flex items-start gap-2">
          <Info className="w-4 h-4 shrink-0 text-indigo-600 mt-0.5" />
          <div>
            <span className="font-semibold">Client Preference Controller:</span>
            <span className="text-indigo-700 ml-1">
              Active for this session. Backend persistent gate-weight profiles API is scheduled for future pipeline release.
            </span>
          </div>
        </div>

        {/* Scrollable Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Sources */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
              Sources
            </label>
            <div className="flex flex-wrap gap-2">
              {["Amazon", "Flipkart", "Myntra", "Meesho", "Nykaa"].map((src) => {
                const active = config.sources.includes(src);
                return (
                  <button
                    key={src}
                    type="button"
                    onClick={() => toggleSource(src)}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                      active
                        ? "bg-indigo-50 border-indigo-300 text-indigo-700"
                        : "bg-white border-slate-200 text-slate-500 hover:border-slate-300"
                    }`}
                  >
                    {src}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Country */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
              Country
            </label>
            <select
              value={config.country}
              onChange={(e) => setConfig({ ...config, country: e.target.value })}
              className="w-full px-3 py-2 text-xs bg-white border border-slate-200 rounded-lg text-slate-800 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
            >
              <option value="India">India</option>
              <option value="USA">USA</option>
              <option value="Europe">Europe</option>
              <option value="UK">United Kingdom</option>
              <option value="GCC_MiddleEast">GCC / Middle East</option>
            </select>
          </div>

          {/* Gates */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-3">
              Gates
            </label>
            <div className="space-y-3">
              {/* Gate 1 */}
              <div className="flex items-center justify-between gap-3 text-xs">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={config.gate1Enabled}
                    onChange={(e) =>
                      setConfig({ ...config, gate1Enabled: e.target.checked })
                    }
                    className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 border-slate-300"
                  />
                  <span className="font-medium text-slate-800">
                    Gate 1: Source scan
                  </span>
                </label>
                <input
                  type="text"
                  value={config.gate1Threshold}
                  onChange={(e) =>
                    setConfig({ ...config, gate1Threshold: e.target.value })
                  }
                  className="w-36 px-2.5 py-1 text-xs border border-slate-200 rounded-md bg-slate-50 text-slate-700"
                />
              </div>

              {/* Gate 2 */}
              <div className="flex items-center justify-between gap-3 text-xs">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={config.gate2Enabled}
                    onChange={(e) =>
                      setConfig({ ...config, gate2Enabled: e.target.checked })
                    }
                    className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 border-slate-300"
                  />
                  <span className="font-medium text-slate-800">
                    Gate 2: Trend velocity
                  </span>
                </label>
                <input
                  type="text"
                  value={config.gate2Threshold}
                  onChange={(e) =>
                    setConfig({ ...config, gate2Threshold: e.target.value })
                  }
                  className="w-36 px-2.5 py-1 text-xs border border-slate-200 rounded-md bg-slate-50 text-slate-700"
                />
              </div>

              {/* Gate 3 */}
              <div className="flex items-center justify-between gap-3 text-xs">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={config.gate3Enabled}
                    onChange={(e) =>
                      setConfig({ ...config, gate3Enabled: e.target.checked })
                    }
                    className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 border-slate-300"
                  />
                  <span className="font-medium text-slate-800">
                    Gate 3: Demand check
                  </span>
                </label>
                <input
                  type="text"
                  value={config.gate3Threshold}
                  onChange={(e) =>
                    setConfig({ ...config, gate3Threshold: e.target.value })
                  }
                  className="w-36 px-2.5 py-1 text-xs border border-slate-200 rounded-md bg-slate-50 text-slate-700"
                />
              </div>

              {/* Gate 4 */}
              <div className="flex items-center justify-between gap-3 text-xs">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={config.gate4Enabled}
                    onChange={(e) =>
                      setConfig({ ...config, gate4Enabled: e.target.checked })
                    }
                    className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 border-slate-300"
                  />
                  <span className="font-medium text-slate-800">
                    Gate 4: Price & margin
                  </span>
                </label>
                <input
                  type="text"
                  value={config.gate4Threshold}
                  onChange={(e) =>
                    setConfig({ ...config, gate4Threshold: e.target.value })
                  }
                  className="w-36 px-2.5 py-1 text-xs border border-slate-200 rounded-md bg-slate-50 text-slate-700"
                />
              </div>

              {/* Gate 5 */}
              <div className="flex items-center justify-between gap-3 text-xs">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={config.gate5Enabled}
                    onChange={(e) =>
                      setConfig({ ...config, gate5Enabled: e.target.checked })
                    }
                    className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 border-slate-300"
                  />
                  <span className="font-medium text-slate-800">
                    Gate 5: AI verification
                  </span>
                </label>
                <input
                  type="text"
                  value={config.gate5Threshold}
                  onChange={(e) =>
                    setConfig({ ...config, gate5Threshold: e.target.value })
                  }
                  className="w-36 px-2.5 py-1 text-xs border border-slate-200 rounded-md bg-slate-50 text-slate-700"
                />
              </div>
            </div>
          </div>

          {/* Score weights */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-3">
              Score weights
            </label>
            <div className="space-y-3">
              <div>
                <div className="flex justify-between text-xs font-medium text-slate-700 mb-1">
                  <span>Trend velocity</span>
                  <span className="font-mono text-indigo-600">
                    {config.weights.trendVelocity}%
                  </span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-indigo-600 h-2 rounded-full"
                    style={{ width: `${config.weights.trendVelocity}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs font-medium text-slate-700 mb-1">
                  <span>Demand</span>
                  <span className="font-mono text-indigo-600">
                    {config.weights.demand}%
                  </span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-indigo-600 h-2 rounded-full"
                    style={{ width: `${config.weights.demand}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs font-medium text-slate-700 mb-1">
                  <span>Price & margin</span>
                  <span className="font-mono text-indigo-600">
                    {config.weights.priceMargin}%
                  </span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-indigo-600 h-2 rounded-full"
                    style={{ width: `${config.weights.priceMargin}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs font-medium text-slate-700 mb-1">
                  <span>AI confidence</span>
                  <span className="font-mono text-indigo-600">
                    {config.weights.aiConfidence}%
                  </span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-indigo-600 h-2 rounded-full"
                    style={{ width: `${config.weights.aiConfidence}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-6 border-t border-slate-100 bg-slate-50 flex items-center justify-between gap-3">
          <Button
            variant="primary"
            onClick={handleSave}
            className="flex-1 bg-indigo-600 hover:bg-indigo-700"
          >
            {savedNotice ? (
              <span className="inline-flex items-center gap-1.5">
                <Check className="w-4 h-4" /> Applied
              </span>
            ) : (
              "Save logic"
            )}
          </Button>
          <Button variant="outline" onClick={handleReset}>
            Reset to default
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
};
