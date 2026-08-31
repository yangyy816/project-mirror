// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DemoVersionHistoryWorkspace } from "./DemoVersionHistoryWorkspace";

afterEach(cleanup);

describe("DemoVersionHistoryWorkspace", () => {
  it("renders the contract-only synthetic boundary and accessible comparison slider", () => {
    render(<DemoVersionHistoryWorkspace />);

    expect(
      screen.getByText("UI_CONTRACT_ONLY", { exact: false }),
    ).toBeVisible();
    expect(
      screen.getByText("REAL_ASSET_RUNTIME_PENDING", { exact: false }),
    ).toBeVisible();
    expect(
      screen.getByText("PRODUCTION_RELEASE_NOT_AUTHORIZED", { exact: false }),
    ).toBeVisible();
    const slider = screen.getByRole("slider", { name: /对比滑杆/ });
    fireEvent.change(slider, { target: { value: "72" } });
    expect(slider).toHaveValue("72");
    expect(slider).toHaveAttribute("aria-valuetext", "当前对比位置 72%");
    expect(screen.getByText("4d5a8f3c…d9a2")).toBeVisible();
    expect(screen.queryByText("4d5a8f3ce1b7d9a2")).toBeNull();
  });

  it("keeps restore and rollback state machines distinct and exposes cancellation and failure", () => {
    render(<DemoVersionHistoryWorkspace />);

    fireEvent.click(screen.getByRole("button", { name: "恢复到所选版本" }));
    expect(screen.getByText(/恢复请求待确认/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "取消" }));
    expect(screen.getByText(/操作已取消/)).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "回滚到父版本" }));
    expect(screen.getByText(/回滚到直接父版本/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "标记失败" }));
    expect(screen.getByText(/操作失败/)).toBeVisible();
  });

  it("keeps the selected published version, parent, and digest internally consistent", () => {
    render(<DemoVersionHistoryWorkspace />);

    fireEvent.click(screen.getByRole("button", { name: /父版本 v3/ }));
    expect(screen.getByText("iv-demo-003")).toBeVisible();
    expect(
      screen.getByText("timeline-version-003 · IMAGE_VERSION"),
    ).toBeVisible();
    expect(screen.getByText("3c1e6a8b…0579")).toBeVisible();
    expect(screen.getByText("none")).toBeVisible();
    expect(screen.getByText(/没有父版本/)).toBeVisible();
    expect(screen.getByRole("button", { name: "回滚到父版本" })).toBeDisabled();
  });

  it("confirms restore and rollback independently for legal published versions", () => {
    render(<DemoVersionHistoryWorkspace />);

    fireEvent.click(screen.getByRole("button", { name: "恢复到所选版本" }));
    fireEvent.click(screen.getByRole("button", { name: "确认完成" }));
    expect(screen.getByText(/恢复已显示为完成/)).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "回滚到父版本" }));
    fireEvent.click(screen.getByRole("button", { name: "确认完成" }));
    expect(screen.getByText(/回滚已显示为完成/)).toBeVisible();
  });

  it("does not claim an unsupported version can be restored", () => {
    render(<DemoVersionHistoryWorkspace />);

    fireEvent.click(screen.getByRole("button", { name: /不支持的执行请求/ }));
    fireEvent.click(screen.getByRole("button", { name: "恢复到所选版本" }));
    expect(screen.getByText(/没有获批执行能力/)).toBeVisible();
    expect(
      screen.getByRole("button", { name: "恢复到所选版本" }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "回滚到父版本" })).toBeDisabled();
  });

  it.each([/已取消执行 v2/, /失败执行 v1/])(
    "fails closed for an unpublished execution event: %s",
    (entryName) => {
      render(<DemoVersionHistoryWorkspace />);

      fireEvent.click(screen.getByRole("button", { name: entryName }));
      expect(screen.getByText(/未发布的 execution event/)).toBeVisible();
      expect(screen.getAllByText("none (not published)")).toHaveLength(2);
      expect(
        screen.getByRole("button", { name: "恢复到所选版本" }),
      ).toBeDisabled();
      expect(
        screen.getByRole("button", { name: "回滚到父版本" }),
      ).toBeDisabled();
    },
  );

  it("makes loading, empty and unavailable presentation states observable without network calls", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<DemoVersionHistoryWorkspace />);

    fireEvent.click(screen.getByRole("button", { name: "LOADING" }));
    expect(screen.getByText("正在加载合成版本呈现状态。")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "EMPTY" }));
    expect(screen.getByText(/没有可显示的 ImageVersion/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "UNAVAILABLE" }));
    expect(screen.getByText(/版本历史当前不可用/)).toBeVisible();
    expect(fetchMock).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it("does not contain browser credential or persistent-storage code", () => {
    const source = readFileSync(
      join(
        process.cwd(),
        "src/components/demo/DemoVersionHistoryWorkspace.tsx",
      ),
      "utf8",
    );
    expect(source).not.toMatch(
      /Bearer|Authorization|localStorage|sessionStorage|indexedDB/,
    );
  });
});
