import Foundation

/// The list editor's state, for both creating and renaming.
struct ListDraft: Equatable {
    var name: String = ""
    var description: String = ""
    var color: Todo_V1_ListColor = .blue
    var visibility: Todo_V1_ListVisibility = .private

    init() {}

    init(list: Todo_V1_TodoList) {
        self.name = list.name
        self.description = list.description_p
        self.color = list.color
        self.visibility = list.visibility
    }

    var trimmedName: String { name.trimmingCharacters(in: .whitespacesAndNewlines) }
    var isValid: Bool { !trimmedName.isEmpty }

    var createRequest: Todo_V1_CreateListRequest {
        Todo_V1_CreateListRequest.with {
            $0.name = trimmedName
            $0.description_p = description.trimmingCharacters(in: .whitespacesAndNewlines)
            $0.color = color
            $0.visibility = visibility
        }
    }

    func updateRequest(id: String) -> Todo_V1_UpdateListRequest {
        Todo_V1_UpdateListRequest.with {
            $0.id = id
            $0.name = trimmedName
            $0.description_p = description.trimmingCharacters(in: .whitespacesAndNewlines)
            $0.color = color
            $0.visibility = visibility
        }
    }
}
