"use client";

import { useMemo } from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

interface ChartData {
  type: "bar" | "line" | "pie";
  title: string;
  data: Array<Record<string, any>>;
  x_key?: string;
  y_key?: string;
  name_key?: string;
  value_key?: string;
  colors?: string[];
}

interface ReportChartsProps {
  charts: ChartData[];
}

const DEFAULT_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#f97316"];

function BarChartComponent({ chart }: { chart: ChartData }) {
  const data = chart.data || [];
  const xKey = chart.x_key || "name";
  const yKey = chart.y_key || "value";
  
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 15, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey={xKey} stroke="#6b7280" fontSize={11} />
          <YAxis stroke="#6b7280" fontSize={11} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#ffffff",
              border: "1px solid #e5e7eb",
              borderRadius: "6px",
              color: "#1f2937",
            }}
          />
          <Bar dataKey={yKey} fill={chart.colors?.[0] || DEFAULT_COLORS[0]} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function LineChartComponent({ chart }: { chart: ChartData }) {
  const data = chart.data || [];
  const xKey = chart.x_key || "name";
  const yKey = chart.y_key || "value";
  
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 15, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey={xKey} stroke="#6b7280" fontSize={11} />
          <YAxis stroke="#6b7280" fontSize={11} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#ffffff",
              border: "1px solid #e5e7eb",
              borderRadius: "6px",
              color: "#1f2937",
            }}
          />
          <Line
            type="monotone"
            dataKey={yKey}
            stroke={chart.colors?.[0] || DEFAULT_COLORS[0]}
            strokeWidth={2}
            dot={{ fill: chart.colors?.[0] || DEFAULT_COLORS[0], strokeWidth: 2, r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function PieChartComponent({ chart }: { chart: ChartData }) {
  const data = chart.data || [];
  const nameKey = chart.name_key || "name";
  const valueKey = chart.value_key || "value";
  const colors = chart.colors || DEFAULT_COLORS;
  
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
            outerRadius={70}
            fill="#8884d8"
            dataKey={valueKey}
            nameKey={nameKey}
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: "#ffffff",
              border: "1px solid #e5e7eb",
              borderRadius: "6px",
              color: "#1f2937",
            }}
          />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function ReportCharts({ charts }: ReportChartsProps) {
  const validCharts = useMemo(() => {
    return charts.filter(chart => 
      chart && 
      chart.type && 
      chart.data && 
      Array.isArray(chart.data) && 
      chart.data.length > 0
    );
  }, [charts]);

  if (!validCharts || validCharts.length === 0) {
    return (
      <div className="p-5 rounded-lg bg-gray-50 border border-gray-200 text-center">
        <p className="text-gray-500 text-sm">暂无图表数据</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {validCharts.map((chart, index) => (
        <div
          key={index}
          className="p-4 rounded-lg bg-white border border-gray-200 shadow-sm"
        >
          <h3 className="text-base font-semibold text-gray-800 mb-3">
            {chart.title || `图表 ${index + 1}`}
          </h3>
          {chart.type === "bar" && <BarChartComponent chart={chart} />}
          {chart.type === "line" && <LineChartComponent chart={chart} />}
          {chart.type === "pie" && <PieChartComponent chart={chart} />}
        </div>
      ))}
    </div>
  );
}

export function parseChartsFromMarkdown(markdown: string): ChartData[] {
  const charts: ChartData[] = [];
  const chartRegex = /```json\s*\n?(\{[\s\S]*?\})\s*\n?```/g;
  let match;
  
  while ((match = chartRegex.exec(markdown)) !== null) {
    try {
      const data = JSON.parse(match[1]);
      if (data.type && data.data && Array.isArray(data.data)) {
        charts.push(data as ChartData);
      }
    } catch {}
  }
  
  return charts;
}
