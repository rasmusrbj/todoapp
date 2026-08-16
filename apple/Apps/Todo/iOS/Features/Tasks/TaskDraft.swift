import Foundation
import SwiftProtobuf

/// What the composer is holding before it is saved.
///
/// One draft type for both creating and editing, because the form is the same
/// either way — but the two produce different requests, and deliberately so:
///
/// * `CreateTaskRequest` takes everything at once, including the checklist,
///   the labels and the assignee.
/// * `UpdateTaskRequest` covers only the plain fields. Status, assignee, labels
///   and which list a task belongs to each have their own RPC, because each has
///   side effects the server owns — completion stamps metadata and rolls a
///   recurrence forward, moving lists drops labels, assigning checks membership.
///   The composer calls those separately rather than pretending one PATCH covers
///   them.
struct TaskDraft: Equatable {
    var listId: String
    var title: String = ""
    var description: String = ""
    var priority: Todo_V1_TaskPriority = .none
    var status: Todo_V1_TaskStatus = .todo
    var assigneeId: String?
    var labelIds: [String] = []
    var dueAt: Date?
    /// False for an all-day task, which is why the time is not simply inferred
    /// from `dueAt` being non-nil.
    var dueHasTime: Bool = false
    var startsAt: Date?
    var recurrence: Todo_V1_RecurrenceFrequency = .none
    var recurrenceInterval: Int = 1
    var estimateMinutes: Int = 0
    var subtaskTitles: [String] = []

    init(listId: String) {
        self.listId = listId
    }

    /// Seeds the form from an existing task, for editing.
    init(task: Todo_V1_Task) {
        self.listId = task.list.id
        self.title = task.title
        self.description = task.description_p
        self.priority = task.priority
        self.status = task.status
        self.assigneeId = task.hasAssignee ? task.assignee.id : nil
        self.labelIds = task.labels.map(\.id)
        self.dueAt = task.hasDueAt ? task.dueAt.date : nil
        self.dueHasTime = task.dueHasTime
        self.startsAt = task.hasStartsAt ? task.startsAt.date : nil
        self.recurrence = task.recurrence.frequency
        self.recurrenceInterval = max(Int(task.recurrence.interval), 1)
        self.estimateMinutes = Int(task.estimateMinutes)
    }

    var trimmedTitle: String { title.trimmingCharacters(in: .whitespacesAndNewlines) }

    /// Whether there is enough here to save. A title is the only hard requirement,
    /// matching the server.
    var isValid: Bool { !trimmedTitle.isEmpty && !listId.isEmpty }

    var repeats: Bool { recurrence.isConcrete && recurrence != .none }

    var createRequest: Todo_V1_CreateTaskRequest {
        Todo_V1_CreateTaskRequest.with {
            $0.listID = listId
            $0.title = trimmedTitle
            $0.description_p = description.trimmingCharacters(in: .whitespacesAndNewlines)
            $0.priority = priority
            $0.status = status
            if let assigneeId, !assigneeId.isEmpty { $0.assigneeID = assigneeId }
            $0.labelIds = labelIds
            if let dueAt {
                $0.dueAt = Google_Protobuf_Timestamp(date: dueAt)
                $0.dueHasTime = dueHasTime
            }
            if let startsAt { $0.startsAt = Google_Protobuf_Timestamp(date: startsAt) }
            if repeats {
                $0.recurrence = .with {
                    $0.frequency = recurrence
                    $0.interval = Int32(max(recurrenceInterval, 1))
                }
            }
            $0.estimateMinutes = Int32(estimateMinutes)
            $0.subtaskTitles = subtaskTitles.filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }
        }
    }

    /// The edit request. Absence and clearing are different things on the wire —
    /// an unset `due_at` means "leave it alone", and `clear_due_at` means "remove
    /// it" — so a form that has emptied the date has to say the second.
    ///
    /// Note `clearDueAt_p` rather than `clearDueAt`: SwiftProtobuf already generates
    /// `clearDueAt()` as the method that unsets the optional `due_at`, so our
    /// `clear_due_at` *field* gets the `_p` suffix to avoid the collision (the same
    /// treatment `description` gets). Assigning `clearDueAt` instead is a compile
    /// error, which is the good outcome — silently calling the wrong one would send
    /// a request that leaves the date exactly where it was.
    func updateRequest(id: String) -> Todo_V1_UpdateTaskRequest {
        Todo_V1_UpdateTaskRequest.with {
            $0.id = id
            $0.title = trimmedTitle
            $0.description_p = description.trimmingCharacters(in: .whitespacesAndNewlines)
            $0.priority = priority
            $0.estimateMinutes = Int32(estimateMinutes)
            $0.recurrence = .with {
                $0.frequency = repeats ? recurrence : .none
                $0.interval = Int32(max(recurrenceInterval, 1))
            }
            if let dueAt {
                $0.dueAt = Google_Protobuf_Timestamp(date: dueAt)
                $0.dueHasTime = dueHasTime
            } else {
                $0.clearDueAt_p = true
            }
            if let startsAt {
                $0.startsAt = Google_Protobuf_Timestamp(date: startsAt)
            } else {
                $0.clearStartsAt_p = true
            }
        }
    }
}
