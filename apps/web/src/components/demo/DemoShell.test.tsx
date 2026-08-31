// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { DemoShell } from "./DemoShell";

afterEach(cleanup);

describe("DemoShell", () => {
  it("renders validated capability data and contract-only boundaries", () => {
    render(
      <DemoShell
        result={{
          kind: "AVAILABLE",
          data: {
            track: "DEMO_PROTOTYPE",
            capabilities: [
              { code: "P5_COMPILER", status: "AVAILABLE" },
              {
                code: "P6_MAKEUP",
                status: "DEFERRED_WITH_EXPLICIT_REASON",
                reason: "Dedicated research gate is pending.",
              },
            ],
          },
        }}
      />,
    );

    expect(screen.getByText("P5_COMPILER")).toBeInTheDocument();
    expect(screen.getByText("AVAILABLE")).toBeInTheDocument();
    expect(
      screen.getByText("REAL_D02_INTEGRATION_PENDING"),
    ).toBeInTheDocument();
    expect(screen.getByText("UI_CONTRACT_ONLY")).toBeInTheDocument();
    expect(screen.getByText(/问卷路由.*UI_CONTRACT_ONLY/)).toBeInTheDocument();
  });

  it("makes the bearer boundary explicit without exposing a credential", () => {
    render(<DemoShell result={{ kind: "AUTH_REQUIRED", data: null }} />);

    expect(screen.getByText("DEMO_AUTH_REQUIRED")).toBeInTheDocument();
    expect(
      screen.getByText(/不会请求、存储或向浏览器暴露 Demo Bearer/),
    ).toBeInTheDocument();
    expect(screen.queryByText("P5_COMPILER")).toBeNull();
  });

  it("does not substitute fixture capability data when the API is unavailable", () => {
    render(<DemoShell result={{ kind: "UNAVAILABLE", data: null }} />);

    expect(screen.getByText("unavailable")).toBeInTheDocument();
    expect(
      screen.getByText(/不会以缓存、fixture 或推测结果替代真实 API 响应/),
    ).toBeInTheDocument();
    expect(screen.queryByText("P5_COMPILER")).toBeNull();
  });
});
