import Foundation

/// `Identifiable` for the generated messages that carry an `id`.
///
/// SwiftUI needs it for `ForEach` and `.sheet(item:)`. The alternative — passing
/// `id: \.id` at every call site and wrapping every sheet payload — is the same
/// information written a hundred times.
///
/// Only messages with a server-assigned id are listed. `UserRef`, `ListRef` and
/// `LabelRef` are deliberately excluded: their `id` points at the referenced object,
/// so two references to the same user in one `ForEach` would collide.
extension Todo_V1_Task: Identifiable {}
extension Todo_V1_Subtask: Identifiable {}
extension Todo_V1_Comment: Identifiable {}
extension Todo_V1_Activity: Identifiable {}
extension Todo_V1_TodoList: Identifiable {}
extension Todo_V1_ListMember: Identifiable {}
extension Todo_V1_Label: Identifiable {}
extension Todo_V1_User: Identifiable {}
extension Todo_V1_Session: Identifiable {}
