# V39.1 Project Execution UX Cleanup

V39.1 cleans the Project Execution page so KDT OS no longer shows every step for every project on one massive dashboard.

## Changes

- Dashboard now shows project cards only.
- Added individual project execution route: `/project_execution/<project_id>`.
- Added project detail JSON route: `/project_execution/<project_id>.json`.
- Current step is highlighted on the project detail page.
- Step list is shown only after opening a project.
- Start/Resume now opens the selected project detail page.
- Mark Complete returns to the project detail page.

## Rule

One project. One next step. One proof requirement.

KDT OS should not overwhelm the user with every project and every step at the same time.
