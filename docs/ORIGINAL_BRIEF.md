## 1. BUSINESS CONCEPT

The platform connects clients who need video editing with our internal team of video editors.

The platform itself DOES NOT automatically edit videos using AI.

Instead, the workflow is:

CLIENT UPLOADS VIDEO → CLIENT SELECTS EDITING REQUIREMENTS → CLIENT PAYS → OUR TEAM RECEIVES PROJECT → PROJECT IS ASSIGNED TO AN EDITOR → EDITOR DOWNLOADS THE SOURCE FILES → EDITOR EDITS THE VIDEO USING THEIR OWN SOFTWARE → EDITOR UPLOADS THE EDITED VIDEO → CLIENT REVIEWS IT → CLIENT REQUESTS REVISION OR ACCEPTS IT → FINAL VIDEO IS DELIVERED → EDITOR RECEIVES COINS.

The platform is therefore primarily a project-management, client-ordering, communication, payment, file-management and editor-management system for a human video-editing service.

Do not create an automatic video-editing engine.

---

# 2. USER ROLES

There should be three major types of users.

### A. CLIENT

Clients can:

* Create an account
* Log in
* Upload videos
* Upload multiple source files if required
* Upload inspiration/reference videos
* Upload images/assets
* Select editing requirements
* Select a song or request a song suggestion
* Choose a predefined editing plan
* Create a customized editing order
* See the calculated price
* Make payment
* Track project status
* Communicate with the team/editor
* Request an editor call
* View edited drafts
* Request revisions
* Approve the final video
* Download the final video
* View previous projects
* View invoices/payment history
* Purchase influencer/monthly packages

---

### B. PRESENTER / ADMIN / OUR TEAM

There will initially be two people managing the business.

The presenter/admin interface should allow us to:

* View all orders
* View all clients
* View all editors
* View project details
* View uploaded files
* View client requirements
* View inspiration material
* View selected songs
* View payment status
* Assign projects to editors
* Reassign projects
* Monitor project progress
* Monitor deadlines
* See projects awaiting assignment
* See projects currently being edited
* See projects waiting for client approval
* See revision requests
* See completed projects
* Manage plans
* Manage pricing
* Manage customization pricing
* Manage influencer packages
* Manage editors
* Manage editor coin values
* Manage coin payouts
* Handle editor call requests
* Handle client support
* Enable/disable certain platform features
* Manage users
* View analytics

The presenter dashboard should provide a complete overview of the business.

---

### C. EDITOR

Editors have a separate dashboard.

When an editor logs in, they should see:

* Assigned projects
* Projects waiting for them
* Project deadlines
* Client requirements
* Source videos/files
* Inspiration videos
* Selected song
* Requested effects
* Color grading requirements
* Quality enhancement requirements
* Other customization requirements
* Client notes
* Call requests
* Revision requests

For each assigned project, the editor can:

1. Open project
2. Download source files
3. Review client requirements
4. Edit the video externally
5. Upload the edited draft
6. Add a note to the client/presenter
7. Submit the draft for client review
8. Receive revision requests
9. Upload revised versions
10. Submit the final version

Once the client accepts the final video, the editor receives coins according to the project's payment/earning rules.

Editors should have a wallet/coin dashboard showing:

* Total coins earned
* Pending coins
* Redeemable coins
* Coins redeemed
* Redemption history
* Redemption requests
* Coin transaction history

The exact monetary value of each coin will be provided later.

---

# 3. CLIENT LANDING PAGE

Create a professional, visually attractive landing page focused on video editing.

The website should immediately communicate that users can send their videos to professional editors and receive professionally edited videos.

Possible sections:

* Hero section
* How it works
* Editing services
* Plans
* Custom editing
* Influencer packages
* Why choose us
* 24-hour delivery
* Revision support
* Editor consultation
* Testimonials
* FAQ
* Call to action
* Footer

The design should feel premium, modern and creator-focused.

Do not make it look like a generic SaaS dashboard.

The target audience includes:

* Instagram creators
* Influencers
* Students
* Businesses
* Personal brands
* Content creators
* People who want professional reels
* People who don't know how to edit videos themselves

---

# 4. VIDEO ORDER FLOW

The client should be able to start a new editing order.

### STEP 1 — UPLOAD

Allow users to upload:

* Video files
* Multiple video files
* Images
* Reference/inspiration videos
* Other assets

Display upload progress.

Validate supported file types and file sizes.

---

### STEP 2 — EDITING REQUIREMENTS

Give clients selectable options such as:

☐ Color grading
☐ Improve video quality
☐ Add transitions
☐ Add effects
☐ Add subtitles/captions
☐ Remove unwanted portions
☐ Add text
☐ Add graphics
☐ Add slow motion
☐ Add speed ramps
☐ Add cinematic effects
☐ Audio enhancement
☐ Background music
☐ Other

Also provide an "Other requirements" text box.

The exact available options and pricing should be configurable by the admin.

---

# 5. INSPIRATION / REFERENCE

Clients should be able to upload an inspiration/reference video.

They should also be able to write:

"Make my video similar to this."

Provide a text box for additional explanation.

The editor should be able to access these references from the project dashboard.

---

# 6. SONG SELECTION

Provide multiple options:

○ I will provide my own song
○ I already have a song
○ I want the editor to suggest a song

If the client requests a song suggestion, show a note that the editing team will recommend a song that suits the video/reel.

Allow the client to upload an audio file or provide song information where appropriate.

---

# 7. EDITING PLANS

Create a Plans section with THREE plans.

The exact names, features and prices will be provided later.

Therefore, build the system so that the admin can easily configure:

* Plan name
* Price
* Features
* Number of revisions
* Delivery time
* Video duration limits
* Priority level
* Color grading availability
* Quality enhancement
* Effects
* Song suggestion
* Other services

Do NOT hard-code the final prices because they will be provided later.

Each plan should have:

* Plan name
* Price
* Feature list
* Select button

---

# 8. CUSTOM ORDER

Clients should also have a "Customize Your Video" option.

Instead of selecting a predefined plan, they can select individual services using checkboxes.

Example:

☐ Color grading
☐ Quality enhancement
☐ Effects
☐ Transitions
☐ Captions
☐ Audio enhancement
☐ Song recommendation
☐ Cinematic treatment
☐ Other

Each option can have an admin-configurable price.

The system should dynamically calculate:

BASE PRICE + SELECTED SERVICES = TOTAL PRICE

Display the final amount before payment.

The admin should be able to modify the pricing later.

---

# 9. PAYMENT

The client must pay before the editing process begins.

After successful payment:

* Create an order
* Generate a unique project/order ID
* Store payment details
* Change order status to "Payment Completed"
* Make the project visible to the presenter/admin
* Allow the presenter to assign an editor

Do not begin the editing workflow until payment is confirmed.

Payment gateway integration should be structured so that the actual provider can be configured later.

---

# 10. PROJECT STATUS

Every project should have a clearly visible status.

Possible statuses:

1. Payment Pending
2. Payment Completed
3. Awaiting Editor Assignment
4. Editor Assigned
5. Editing in Progress
6. Draft Uploaded
7. Awaiting Client Review
8. Revision Requested
9. Revision in Progress
10. Final Video Uploaded
11. Completed
12. Cancelled

The client, presenter and editor should each see the status relevant to them.

---

# 11. 24-HOUR DELIVERY

The service promises delivery within 24 hours.

When the order is created, record:

* Order creation time
* Payment completion time
* Expected delivery time
* Current status

Show a countdown/deadline indicator in the presenter and editor dashboards.

Highlight:

* Due soon
* On time
* Overdue

The presenter should be able to monitor all active projects and identify delayed orders.

---

# 12. EDITOR ASSIGNMENT

The presenter/admin can manually assign an editor to a project.

Show:

* Project ID
* Client
* Plan
* Requirements
* Deadline
* Assigned editor
* Current status

Allow reassignment when required.

---

# 13. AI-BASED PROJECT COMPLEXITY ANALYSIS

The platform should include an AI-based project classification system.

The AI should analyze the client's submitted editing requirements and determine the approximate complexity/proficiency level required.

The three editor proficiency levels are:

### BEGINNER

Suitable for relatively simple editing tasks, such as:

* Basic cuts
* Simple transitions
* Basic trimming
* Simple text
* Basic music synchronization
* Minor adjustments

### INTERMEDIATE

Suitable for:

* More complex transitions
* Advanced text/graphics
* More detailed synchronization
* Moderate color grading
* More complex effects
* Multiple editing requirements

### ADVANCED

Suitable for:

* Complex cinematic edits
* Advanced color grading
* Complex visual effects
* Advanced motion graphics
* Highly detailed editing
* Complex storytelling
* Multiple advanced requirements
* Projects requiring significant editing expertise

The exact classification criteria should be configurable and should be improved over time based on project data.

The AI should analyze information such as:

* Selected editing options
* Client's written requirements
* Inspiration/reference information
* Video duration
* Number of uploaded clips
* Requested effects
* Color grading requirements
* Audio requirements
* Number of requested components
* Other relevant project metadata

The AI should output a project complexity level:

BEGINNER / INTERMEDIATE / ADVANCED

The AI classification should NOT directly expose sensitive internal information to the client.

The presenter/admin should be able to see and override the AI classification when necessary.

---

# 14. EDITOR REGISTRATION AND PROFICIENCY

Every editor must register on the platform.

Editor registration should collect relevant information such as:

* Name
* Email
* Phone number
* Password
* Editing experience
* Editing software/tools used
* Portfolio
* Previous work samples
* Areas of expertise
* Availability
* Other relevant information

Each editor should have a proficiency level:

* Beginner
* Intermediate
* Advanced

The platform should allow the presenter/admin to approve and classify editors.

The proficiency level should NOT simply be trusted based on what an editor enters during registration.

The presenter/admin should have the ability to review their portfolio and assign/approve their proficiency level.

The admin should be able to change the proficiency level later.

---

# 15. INTELLIGENT EDITOR ASSIGNMENT

When a new client project is paid and ready for editing:

1. Analyze the project using the AI complexity classification system.
2. Determine whether it requires a Beginner, Intermediate or Advanced editor.
3. Find editors belonging to the appropriate proficiency group.
4. Check editor availability.
5. Check whether the editor is currently working on another active project.
6. Assign the project according to the platform's assignment algorithm.

An editor who is currently actively working on a project should be considered occupied and should not receive another simultaneous project if their configured workload capacity is one active project at a time.

If no suitable editor is immediately available:

* Keep the project in a waiting queue, OR
* Assign it to another suitable available editor according to configured rules.

The presenter/admin should be able to see all waiting projects.

---

# 16. ROUND-ROBIN EDITOR ASSIGNMENT

Within each proficiency group, use a round-robin assignment mechanism.

Example:

Suppose there are 10 eligible editors:

Editor 1
Editor 2
Editor 3
Editor 4
Editor 5
Editor 6
Editor 7
Editor 8
Editor 9
Editor 10

The first project is assigned to Editor 1.

The second project is assigned to Editor 2.

If Editor 1 finishes their project before the third project arrives, the third project should NOT automatically return to Editor 1.

Instead, continue the round-robin sequence:

Project 1 → Editor 1
Project 2 → Editor 2
Project 3 → Editor 3
Project 4 → Editor 4
...
Project 10 → Editor 10
Project 11 → Editor 1
Project 12 → Editor 2

The assignment pointer should continue sequentially regardless of whether an earlier editor becomes free.

However, if the next editor in the round-robin sequence is currently occupied, the system should handle this according to the configured queue logic.

Possible behavior:

* Keep the project waiting for that editor, OR
* Skip temporarily unavailable editors and assign to the next eligible available editor.

This behavior should be configurable by the presenter/admin.

The system must maintain a persistent round-robin pointer so that assignments remain fair across projects.

The pointer should be maintained separately for each proficiency level.

For example:

Beginner round-robin queue
Intermediate round-robin queue
Advanced round-robin queue

This ensures that Beginner projects are distributed fairly among Beginner editors, Intermediate projects among Intermediate editors, and Advanced projects among Advanced editors.

---

# 17. EDITOR WORKLOAD

Each editor should have an availability status:

* Available
* Busy
* Offline
* On Leave
* Temporarily Unavailable

The editor's active project count should be visible to the presenter/admin.

The assignment system should consider:

* Proficiency
* Availability
* Active project count
* Round-robin position
* Project complexity
* Deadline

The admin should be able to manually override automatic assignment.

---

# 18. CLIENT REVIEW AND REVISION

When the editor uploads a draft:

The client receives a notification that their edited video is ready for review.

The client can:

### ACCEPT

Accept the video and mark the project as completed.

### REQUEST REVISION

The client can enter detailed revision instructions.

Example:

"Please change the transition at 00:07 and use the song starting from the chorus."

The revision request should become visible to the editor and presenter.

Each uploaded version should be stored separately so the system maintains version history.

Example:

Version 1
Version 2
Version 3
Final

---

# 19. EDITOR CONSULTATION / CALL

During checkout, allow the client to select:

☐ I want to talk to an editor before editing

and/or:

☐ I want to talk to an editor after the draft is ready

If selected, create a call request visible to the presenter/admin.

The presenter should be able to:

* View the request
* Assign an editor
* Schedule the call
* Mark it as completed

The actual video-call technology can be integrated later.

---

# 20. INFLUENCER SECTION

Create a separate section for influencers and recurring creators.

They should be able to purchase monthly editing packages.

The package system should support:

* Monthly subscription/package
* Number of videos/reels
* Number of revisions
* Priority editing
* Dedicated editor
* Additional services

The exact packages and pricing will be provided later.

Design the system so these can be configured from the admin dashboard.

---

# 21. FILE MANAGEMENT

Each project should have a dedicated file area.

Organize files into:

### CLIENT FILES

* Original videos
* Images
* Audio
* Inspiration/reference
* Other assets

### EDITOR FILES

* Draft 1
* Draft 2
* Revised versions
* Final video

Do not overwrite old versions.

The system should maintain version history.

---

# 22. CRITICAL VIDEO QUALITY REQUIREMENT

This is one of the most important technical requirements of the entire platform.

The website MUST NOT unnecessarily deteriorate, compress, resize, transcode or reduce the quality of videos uploaded by either clients or editors.

The original uploaded file must be preserved exactly.

The system should prioritize:

* Original resolution preservation
* Original frame-rate preservation
* Original bitrate preservation
* Original codec preservation where technically possible
* Original audio quality preservation
* Original file integrity
* No unnecessary re-encoding
* No automatic compression
* No automatic resolution reduction
* No automatic conversion to lower-quality preview files as a replacement for the original

If previews or thumbnails are generated for UI purposes, they must be separate derivatives.

The original file must always remain preserved and available for download.

If a preview needs transcoding for browser playback, the preview must NOT replace the original source file.

The final video uploaded by the editor must also be preserved in its original uploaded quality.

The platform should use direct/streamed file uploads where appropriate rather than processing large video files unnecessarily through the application server.

The architecture should support large video files efficiently.

The storage system should preserve the original files without quality loss.

The user should be clearly informed that the platform preserves uploaded video quality.

Quality preservation is a core product requirement and should be treated as a higher priority than reducing storage or bandwidth costs.

---

# 23. STRICT FILE PRIVACY AND ACCESS CONTROL

Uploaded videos and project files are private.

A client's uploaded video must ONLY be accessible to:

* That specific client
* The assigned editor
* Authorized presenter/admin users

A client's uploaded files must NOT be visible to:

* Other clients
* Other editors
* Unassigned editors
* Public visitors
* Search engines
* Unauthorized users

Similarly, an editor's uploaded edited video must only be visible to:

* The corresponding client
* The assigned editor
* Authorized presenter/admin users

Do not expose raw public file URLs.

Use authenticated and authorized access to files.

Use secure/private storage buckets or equivalent protected storage.

Use signed/temporary URLs or another secure mechanism for downloading/streaming files where appropriate.

Verify authorization on the server/backend before allowing access to every project file.

Do not rely solely on frontend restrictions.

A user should never be able to access another user's file simply by modifying a URL, project ID or file ID.

Implement proper role-based and project-level access control.

---

# 24. FILE SECURITY

Files should be protected both in storage and during access.

Consider:

* Private storage
* Authentication
* Authorization
* Signed URLs
* Expiring download links
* Secure upload endpoints
* File-type validation
* File-size validation
* Malware/security scanning where appropriate
* Access logging
* Audit trails

The system should never make uploaded client videos publicly accessible by default.

---

# 25. NOTIFICATIONS

Provide notifications for important events.

CLIENT:

* Payment successful
* Editor assigned
* Editing started
* Draft ready
* Revision submitted
* Final video ready
* Project completed
* Call request update

EDITOR:

* New project assigned
* Deadline approaching
* Revision requested
* Client accepted
* Payment/coins credited

PRESENTER:

* New order
* Payment received
* Unassigned project
* Deadline approaching
* Revision requested
* Call request
* Completed project

---

# 26. ADMIN ANALYTICS

The presenter dashboard should include useful business metrics.

Examples:

* Total orders
* Active projects
* Completed projects
* Pending projects
* Revenue
* Orders today
* Orders this month
* Average delivery time
* Revision rate
* Active editors
* Editor workload
* Pending payouts
* Influencer packages
* Customer retention

Use clear dashboard cards and charts where appropriate.

---

# 27. DATABASE / BACKEND STRUCTURE

Design the backend/database around entities such as:

Users
Clients
Editors
Admins/Presenters
Projects
Orders
Plans
Custom Services
Payments
Files
Project Versions
Revision Requests
Editor Assignments
Call Requests
Influencer Packages
Subscriptions/Packages
Notifications
Editor Coins
Coin Transactions
Redemption Requests
Editor Availability
Editor Proficiency
Project Complexity
Assignment Queue
Round-Robin State
Audit Logs

Use proper relationships between these entities.

For example:

User → Projects
Project → Files
Project → Editor
Project → Payment
Project → Revisions
Project → Versions
Editor → Coin Transactions
Editor → Availability
Editor → Proficiency
Project → Complexity Classification
Proficiency Group → Assignment Queue

Maintain a persistent assignment state so that round-robin allocation continues correctly even after server restarts.

---

# 28. SECURITY

Implement proper authentication and role-based authorization.

A client must NOT be able to access:

* Other clients' projects
* Editor dashboard
* Admin dashboard
* Other users' files
* Internal editor information

Editors must only access projects assigned to them.

Presenters/admins should have broader access according to their permissions.

Uploaded files should not be publicly accessible without authorization.

All sensitive operations should be validated on the backend.

---

# 29. AUDIT LOGGING

Maintain internal audit logs for important actions.

Examples:

* Client uploaded file
* Client placed order
* Payment confirmed
* Project assigned
* Project reassigned
* Editor downloaded file
* Editor uploaded draft
* Client requested revision
* Client accepted project
* Coins credited
* Coins redeemed
* Admin changed editor proficiency
* Admin manually overrode AI classification
* Admin manually reassigned project

Audit logs should help the business understand what happened to a project at every stage.

---

# 30. RESPONSIVE DESIGN

The platform must work properly on:

* Desktop
* Laptop
* Tablet
* Mobile

The client-facing website should be particularly mobile-friendly because many users will upload and access reels from mobile devices.

The presenter and editor dashboards can be optimized primarily for desktop while remaining responsive.

---

# 31. DESIGN DIRECTION

Use a premium creator-economy aesthetic.

The UI should feel:

* Modern
* Clean
* Premium
* Creative
* Professional
* Easy to understand

Avoid making the platform look like a boring corporate administration system.

Use strong visual hierarchy, video thumbnails, project cards, progress indicators, status badges and clean dashboards.

The client experience should be simple enough for someone who has never used a professional editing service before.

---

# 32. IMPORTANT BUSINESS RULE

The website is NOT an automated video editor.

It is a managed human video-editing service.

The platform's job is to manage:

CLIENT → ORDER → PAYMENT → REQUIREMENTS → FILES → AI COMPLEXITY ANALYSIS → SUITABLE EDITOR → ROUND-ROBIN ASSIGNMENT → EDITING → REVIEW → REVISION → APPROVAL → DELIVERY → EDITOR PAYMENT/COINS.

---

# 33. CONFIGURABILITY

Do not hard-code business decisions that have not yet been finalized.

The following will be provided later:

* Three plan names
* Plan prices
* Plan features
* Custom-service prices
* Influencer package prices
* Revision limits
* Video-duration limits
* Coin value
* Editor payout rules
* Maximum upload sizes
* Exact delivery rules
* AI complexity rules
* Editor proficiency criteria
* Editor workload limits
* Assignment rules

Build the system so these can be changed through the admin interface without rebuilding the entire application.

---

# 34. INITIAL IMPLEMENTATION PRIORITY

Prioritize functionality over unnecessary complexity.

The first version should successfully support:

1. Client registration/login
2. Client video upload
3. Editing requirement selection
4. Inspiration upload
5. Song selection
6. Plan selection
7. Custom pricing
8. Payment flow
9. Project creation
10. Presenter/admin dashboard
11. Editor registration
12. Editor proficiency management
13. Editor dashboard
14. AI project complexity classification
15. Intelligent editor assignment
16. Round-robin assignment
17. Editor availability tracking
18. Editor file upload
19. Client review
20. Revision requests
21. Final approval
22. Editor coin system
23. Project status tracking
24. Notifications
25. 24-hour deadline tracking
26. Secure project-level file access
27. Original video quality preservation
28. File/version history

Build the architecture in a way that additional features can be added later.

Do not assume the final pricing, plans or coin conversion values.

The final product should feel like a real commercial video-editing service platform rather than a simple portfolio website.

---

# 35. IMPORTANT IMPLEMENTATION PRINCIPLES

When implementing this platform:

### DO:

* Preserve original video files
* Use private file storage
* Enforce server-side authorization
* Maintain project-level access control
* Maintain file versions
* Maintain audit logs
* Maintain persistent editor assignment state
* Use AI only for project complexity classification/assignment
* Allow admin override of AI decisions
* Keep pricing configurable
* Keep editor proficiency configurable
* Keep assignment rules configurable
* Keep coin values configurable
* Keep plans configurable
* Design for large video files
* Design for scalability
* Make the client experience extremely simple

### DO NOT:

* Automatically edit client videos
* Compress original videos unnecessarily
* Replace original files with low-quality previews
* Make uploaded videos publicly accessible
* Allow one client to see another client's files
* Allow an editor to see projects that aren't assigned to them
* Assign every project to the first available editor
* Reset the round-robin assignment pointer whenever an editor becomes available
* Hard-code final pricing
* Hard-code final coin values
* Hard-code final plan details

The core principle is:

*HIGH-QUALITY VIDEO + PRIVACY + FAIR EDITOR ALLOCATION + HUMAN EDITING + SIMPLE CLIENT EXPERIENCE.*