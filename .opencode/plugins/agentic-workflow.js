/**
 * agentic-workflow plugin for OpenCode.
 *
 * Registers skills/ via config.skills.paths, and does nothing else.
 *
 * Only skills/ is registered. evals/ also holds files an agent could read as
 * instructions, but they are regression scenarios that measure these skills,
 * not skills a session should be able to invoke.
 */

import path from "path"
import { fileURLToPath } from "url"

const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..")
const SKILLS_DIR = path.join(PACKAGE_ROOT, "skills")

const AgenticWorkflowPlugin = async () => {
  return {
    config: async (config) => {
      config.skills = config.skills || {}
      config.skills.paths = config.skills.paths || []
      if (!config.skills.paths.includes(SKILLS_DIR)) {
        config.skills.paths.push(SKILLS_DIR)
      }
    },
  }
}

// OpenCode treats every module export as a plugin, so the plugin function is
// this module's only export.
export default AgenticWorkflowPlugin
