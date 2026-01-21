# Tasks: Project Roadmap Management

## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [ ] 1.3 Review and get approval

## 2. Schema Implementation (Phase 2)

- [ ] 2.1 Define roadmap schema structure in code comments/documentation
- [ ] 2.2 Add roadmap validation helper function
- [ ] 2.3 Ensure backward compatibility with empty `roadmap: {}` data

## 3. API Implementation (Phase 2)

- [ ] 3.1 Implement `GET /api/project/<name>/roadmap` endpoint
- [ ] 3.2 Implement `POST /api/project/<name>/roadmap` endpoint
- [ ] 3.3 Add request body validation for POST endpoint
- [ ] 3.4 Add appropriate error responses (404, 400)
- [ ] 3.5 Ensure POST preserves non-roadmap project data

## 4. Dashboard UI - Display (Phase 2)

- [ ] 4.1 Add roadmap panel HTML structure to project card template
- [ ] 4.2 Add expand/collapse control and functionality
- [ ] 4.3 Implement roadmap section rendering (next_up, upcoming, later, not_now)
- [ ] 4.4 Add empty state display for missing roadmap data
- [ ] 4.5 Add CSS styling for roadmap panel

## 5. Dashboard UI - Edit Mode (Phase 2)

- [ ] 5.1 Add Edit button to roadmap panel header
- [ ] 5.2 Implement edit mode toggle (display → form inputs)
- [ ] 5.3 Create form inputs for next_up fields (title, why, definition_of_done)
- [ ] 5.4 Create multi-line textarea inputs for list fields
- [ ] 5.5 Add Save and Cancel buttons
- [ ] 5.6 Implement Save action (POST to API, exit edit mode on success)
- [ ] 5.7 Implement Cancel action (discard changes, exit edit mode)
- [ ] 5.8 Add loading indicator during save
- [ ] 5.9 Add success/error feedback messages

## 6. Testing (Phase 3)

- [ ] 6.1 Test GET endpoint with valid project name
- [ ] 6.2 Test GET endpoint with invalid project name (404)
- [ ] 6.3 Test POST endpoint with valid data
- [ ] 6.4 Test POST endpoint with invalid project name (404)
- [ ] 6.5 Test POST endpoint with malformed data (400)
- [ ] 6.6 Test data persistence across server restarts
- [ ] 6.7 Test backward compatibility with empty roadmap
- [ ] 6.8 Test UI expand/collapse functionality
- [ ] 6.9 Test UI edit mode workflow

## 7. Final Verification

- [ ] 7.1 All tests passing
- [ ] 7.2 No linter errors
- [ ] 7.3 Manual verification of full workflow
- [ ] 7.4 Dashboard responsive on 800px-1920px widths
