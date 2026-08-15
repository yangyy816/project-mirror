import childProcess from "node:child_process";
import { EventEmitter } from "node:events";
import { syncBuiltinESMExports } from "node:module";

if (process.platform === "win32") {
  const originalExec = childProcess.exec;
  childProcess.exec = function sandboxAwareExec(command, ...args) {
    if (command !== "net use") {
      return originalExec.call(this, command, ...args);
    }
    const callback = args.find((argument) => typeof argument === "function");
    const processStub = new EventEmitter();
    queueMicrotask(() => {
      if (callback) {
        callback(
          new Error("network-drive discovery disabled for deterministic tests"),
          "",
          "",
        );
      }
      processStub.emit("close", 1);
    });
    return processStub;
  };
  syncBuiltinESMExports();
}
